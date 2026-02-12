"""
Command-line interface for gcg.

Provides the main entry point and argument parsing for all commands.
"""

import argparse
import os
import re
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Optional

from gcg import __version__
from gcg.book import (
    BookOpenError,
    InvalidPatternError,
    get_account_by_pattern,
    get_split_by_guid,
    get_transaction_by_guid,
    get_transaction_notes,
    get_transaction_notes_batch,
    open_gnucash_book,
)
from gcg.config import Config, load_config
from gcg.output import (
    AccountRow,
    OutputFormatter,
    SplitRow,
    TransactionRow,
)
from gcg.shared import (
    account_name as _account_name,
    prune_to_matching_paths as _prune_to_matching_paths,
    sort_rows as _sort_rows,
    sort_tx_rows as _sort_tx_rows,
    splits_to_rows as _shared_splits_to_rows,
    splits_to_transactions as _shared_splits_to_transactions,
)


def parse_date(date_str: str) -> date:
    """Parse a date string in YYYY-MM-DD format."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError as e:
        raise argparse.ArgumentTypeError(
            f"Invalid date format: {date_str}. Use YYYY-MM-DD."
        ) from e


def parse_date_range(range_str: str) -> tuple[Optional[date], Optional[date]]:
    """
    Parse a date range string like 'A..B', 'A..', or '..B'.

    Returns (start_date, end_date) where either may be None.
    For --date semantics, both start and end are inclusive.
    """
    if ".." not in range_str:
        raise argparse.ArgumentTypeError(
            f"Invalid date range: {range_str}. Use format A..B, A.., or ..B"
        )

    parts = range_str.split("..", 1)
    start_str, end_str = parts[0].strip(), parts[1].strip()

    start_date = parse_date(start_str) if start_str else None
    end_date = parse_date(end_str) if end_str else None

    return (start_date, end_date)


def parse_amount_range(
    range_str: str,
) -> tuple[Optional[Decimal], Optional[Decimal]]:
    """
    Parse an amount range string like 'MIN..MAX', 'MIN..', or '..MAX'.

    Returns (min_amount, max_amount) where either may be None.
    """
    if ".." not in range_str:
        raise argparse.ArgumentTypeError(
            f"Invalid amount range: {range_str}. "
            f"Use format MIN..MAX, MIN.., or ..MAX"
        )

    parts = range_str.split("..", 1)
    min_str, max_str = parts[0].strip(), parts[1].strip()

    try:
        min_amount = Decimal(min_str) if min_str else None
        max_amount = Decimal(max_str) if max_str else None
    except InvalidOperation as e:
        raise argparse.ArgumentTypeError(
            f"Invalid amount in range: {range_str}"
        ) from e

    return (min_amount, max_amount)


def create_parser() -> argparse.ArgumentParser:
    """Create the main argument parser."""
    parser = argparse.ArgumentParser(
        prog="gcg",
        description="Grep-like search and reporting for GnuCash SQLite books",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Start interactive REPL mode",
    )
    parser.add_argument(
        "--book", metavar="PATH", help="Path to GnuCash SQLite file"
    )
    parser.add_argument(
        "--format",
        choices=["table", "csv", "json"],
        default="table",
        help="Output format (default: table)",
    )
    parser.add_argument(
        "--no-header",
        action="store_true",
        help="Omit header row in table/CSV output",
    )
    parser.add_argument(
        "--sort",
        choices=["date", "amount", "account", "description"],
        default="date",
        help="Sort key (default: date)",
    )
    parser.add_argument(
        "--reverse", action="store_true", help="Reverse sort order"
    )
    parser.add_argument(
        "--limit", type=int, metavar="N", help="Limit output to N rows"
    )
    parser.add_argument(
        "--offset", type=int, metavar="N", help="Skip first N rows"
    )
    parser.add_argument(
        "--full-account",
        action="store_true",
        help="Show full account paths (default: short names)",
    )

    # Set defaults for subparser-specific attributes so that
    # commands can use args.X directly instead of getattr/hasattr.
    parser.set_defaults(
        no_subtree=False,
        after=None,
        before=None,
        date=None,
        base_currency=None,
        fx_lookback=None,
        also_original=False,
        currency="auto",
        signed=False,
        context="full",
        full_tx=False,
        regex=False,
        case_sensitive=False,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # accounts command
    accounts_parser = subparsers.add_parser(
        "accounts", help="Search accounts by pattern"
    )
    accounts_parser.add_argument(
        "pattern",
        nargs="?",
        default="",
        help="Account name pattern (substring match by default)",
    )
    accounts_parser.add_argument(
        "--regex", action="store_true", help="Treat pattern as regex"
    )
    accounts_parser.add_argument(
        "--case-sensitive",
        action="store_true",
        help="Use case-sensitive matching",
    )
    accounts_parser.add_argument(
        "--tree", action="store_true", help="Render as account tree"
    )
    accounts_parser.add_argument(
        "--tree-prune",
        action="store_true",
        help="Show tree pruned to matching paths with full subtrees",
    )
    accounts_parser.add_argument(
        "--max-depth", type=int, metavar="N", help="Limit tree depth"
    )
    accounts_parser.add_argument(
        "--show-guids",
        action="store_true",
        help="Include account GUIDs in output",
    )

    # grep command
    grep_parser = subparsers.add_parser(
        "grep", help="Search splits/transactions for text"
    )
    grep_parser.add_argument("text", help="Text to search for")
    grep_parser.add_argument(
        "--regex", action="store_true", help="Treat text as regex"
    )
    grep_parser.add_argument(
        "--case-sensitive",
        action="store_true",
        help="Use case-sensitive matching",
    )
    grep_parser.add_argument(
        "--in",
        dest="search_fields",
        default="desc,memo,notes",
        help="Fields to search: desc,memo,notes (default: all)",
    )
    grep_parser.add_argument(
        "--account",
        metavar="PATTERN",
        help="Restrict to accounts matching pattern",
    )
    grep_parser.add_argument(
        "--account-regex", action="store_true", help="Account pattern is regex"
    )
    grep_parser.add_argument(
        "--no-subtree",
        action="store_true",
        help="Don't include descendant accounts",
    )
    grep_parser.add_argument(
        "--after",
        type=parse_date,
        metavar="YYYY-MM-DD",
        help="Filter: posted on or after date (inclusive)",
    )
    grep_parser.add_argument(
        "--before",
        type=parse_date,
        metavar="YYYY-MM-DD",
        help="Filter: posted before date (exclusive)",
    )
    grep_parser.add_argument(
        "--date",
        type=parse_date_range,
        metavar="A..B",
        help="Date range (inclusive both ends)",
    )
    grep_parser.add_argument(
        "--amount",
        type=parse_amount_range,
        metavar="MIN..MAX",
        help="Amount range filter",
    )
    grep_parser.add_argument(
        "--signed",
        action="store_true",
        help="Use signed amounts (default: absolute)",
    )
    grep_parser.add_argument(
        "--full-tx",
        action="store_true",
        help="Show full transactions containing matches",
    )
    grep_parser.add_argument(
        "--dedupe",
        choices=["tx", "split"],
        default="split",
        help="Deduplication mode (default: split)",
    )
    grep_parser.add_argument(
        "--context",
        choices=["balanced", "full"],
        default="full",
        help="Context mode for --full-tx (default: full)",
    )
    _add_currency_args(grep_parser)

    # ledger command
    ledger_parser = subparsers.add_parser(
        "ledger", help="Display ledger for accounts"
    )
    ledger_parser.add_argument("account_pattern", help="Account name pattern")
    ledger_parser.add_argument(
        "--account-regex", action="store_true", help="Account pattern is regex"
    )
    ledger_parser.add_argument(
        "--no-subtree",
        action="store_true",
        help="Don't include descendant accounts",
    )
    ledger_parser.add_argument(
        "--after",
        type=parse_date,
        metavar="YYYY-MM-DD",
        help="Filter: posted on or after date",
    )
    ledger_parser.add_argument(
        "--before",
        type=parse_date,
        metavar="YYYY-MM-DD",
        help="Filter: posted before date",
    )
    ledger_parser.add_argument(
        "--date", type=parse_date_range, metavar="A..B", help="Date range"
    )
    ledger_parser.add_argument(
        "--amount",
        type=parse_amount_range,
        metavar="MIN..MAX",
        help="Amount range filter",
    )
    ledger_parser.add_argument(
        "--signed", action="store_true", help="Use signed amounts"
    )
    _add_currency_args(ledger_parser)

    # tx command
    tx_parser = subparsers.add_parser("tx", help="Display transaction by GUID")
    tx_parser.add_argument("guid", help="Transaction GUID")

    # split command
    split_parser = subparsers.add_parser("split", help="Display split by GUID")
    split_parser.add_argument("guid", help="Split GUID")

    # doctor command
    subparsers.add_parser("doctor", help="Print diagnostic info")

    # cache command
    cache_parser = subparsers.add_parser("cache", help="Manage sidecar cache")
    cache_parser.add_argument(
        "action", choices=["build", "status", "drop"], help="Cache action"
    )
    cache_parser.add_argument(
        "--force", action="store_true", help="Force rebuild cache"
    )

    # repl command (alternative to -i)
    subparsers.add_parser("repl", help="Start interactive REPL mode")

    return parser


def _add_currency_args(parser: argparse.ArgumentParser) -> None:
    """Add currency-related arguments to a parser."""
    parser.add_argument(
        "--currency",
        choices=["auto", "base", "split", "account"],
        default="auto",
        help="Currency display mode (default: auto)",
    )
    parser.add_argument(
        "--base-currency",
        metavar="CUR",
        help="Base currency for conversions (default: EUR)",
    )
    parser.add_argument(
        "--also-original",
        action="store_true",
        help="Show original currency alongside converted",
    )
    parser.add_argument(
        "--fx-lookback",
        type=int,
        metavar="DAYS",
        help="Max days to look back for exchange rates",
    )


def resolve_date_filters(args) -> tuple[Optional[date], Optional[date]]:
    """
    Resolve date filters from --after/--before/--date args.

    --after is inclusive, --before is exclusive.
    --date A..B is inclusive on both ends (converted to after/before).
    """
    after_date = args.after
    before_date = args.before
    date_range = args.date

    if date_range:
        range_start, range_end = date_range
        if range_start:
            after_date = range_start
        if range_end:
            # --date end is inclusive, so add 1 day for before
            before_date = range_end + timedelta(days=1)

    return (after_date, before_date)


def cmd_accounts(args, config: Config) -> int:
    """Handle the accounts command."""
    try:
        with open_gnucash_book(config.resolve_book_path()) as (book, info):
            try:
                accounts = get_account_by_pattern(
                    book,
                    args.pattern,
                    is_regex=args.regex,
                    case_sensitive=args.case_sensitive,
                    include_subtree=not args.no_subtree,
                )
            except InvalidPatternError as e:
                print(f"Error: {e}", file=sys.stderr)
                return 2

            if not accounts:
                return 1  # No matches

            # Sort accounts by full name
            accounts.sort(key=lambda a: a.fullname)

            # Apply tree-prune if requested
            if args.tree_prune:
                accounts = _prune_to_matching_paths(accounts, book)

            # Convert to output rows
            rows = []
            for acc in accounts:
                depth = acc.fullname.count(":") if args.tree else 0
                if args.tree and args.max_depth is not None:
                    if depth > args.max_depth:
                        continue
                rows.append(
                    AccountRow(
                        name=acc.fullname,
                        type=acc.type,
                        currency=(
                            acc.commodity.mnemonic if acc.commodity else ""
                        ),
                        guid=acc.guid if args.show_guids else None,
                        depth=depth,
                    )
                )

            # Apply limit/offset
            if args.offset:
                rows = rows[args.offset :]
            if args.limit:
                rows = rows[: args.limit]

            formatter = OutputFormatter(
                format_type=args.format,
                show_header=not args.no_header,
                show_guids=args.show_guids,
            )
            formatter.format_accounts(rows, tree_mode=args.tree)
            return 0

    except BookOpenError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2


def cmd_grep(args, config: Config) -> int:
    """Handle the grep command."""
    # Compile search pattern
    flags = 0 if args.case_sensitive else re.IGNORECASE
    if args.regex:
        try:
            pattern = re.compile(args.text, flags)
        except re.error as e:
            print(f"Invalid regex: {e}", file=sys.stderr)
            return 2
    else:
        # Escape for literal match
        pattern = re.compile(re.escape(args.text), flags)

    # Parse search fields
    search_fields = set(args.search_fields.split(","))

    # Resolve date filters
    after_date, before_date = resolve_date_filters(args)

    # Amount range
    amount_range = args.amount if args.amount else (None, None)

    try:
        with open_gnucash_book(config.resolve_book_path()) as (book, info):
            # Filter accounts if specified
            if args.account:
                try:
                    accounts = get_account_by_pattern(
                        book,
                        args.account,
                        is_regex=args.account_regex,
                        case_sensitive=False,
                        include_subtree=not args.no_subtree,
                    )
                except InvalidPatternError as e:
                    print(f"Error: {e}", file=sys.stderr)
                    return 2
                account_set = set(accounts)
            else:
                accounts = [
                    a
                    for a in book.accounts
                    if a.type not in ("ROOT", "TRADING")
                ]
                account_set = None

            # Check notes support
            notes_supported = info.has_notes_column or info.has_slots_notes
            search_notes = "notes" in search_fields and notes_supported
            if "notes" in search_fields and not notes_supported:
                print(
                    "Warning: Notes not supported in this book schema",
                    file=sys.stderr,
                )
                search_fields.discard("notes")

            # Pre-fetch all notes if we need to search them
            notes_map: dict[str, str] = {}
            if search_notes:
                all_tx_guids = set()
                for acc in accounts:
                    for split in acc.splits:
                        all_tx_guids.add(split.transaction.guid)
                notes_map = get_transaction_notes_batch(
                    config.resolve_book_path(),
                    list(all_tx_guids),
                    info.has_notes_column,
                )

            # Collect matching splits
            matching_splits = []
            seen_tx_guids = set()

            for acc in accounts:
                for split in acc.splits:
                    tx = split.transaction

                    # Account filter
                    if account_set and split.account not in account_set:
                        continue

                    # Date filter
                    tx_date = tx.post_date
                    if after_date and tx_date < after_date:
                        continue
                    if before_date and tx_date >= before_date:
                        continue

                    # Amount filter
                    split_value = Decimal(str(split.value))
                    if not args.signed:
                        split_value = abs(split_value)
                    min_amt, max_amt = amount_range
                    if min_amt is not None and split_value < min_amt:
                        continue
                    if max_amt is not None and split_value > max_amt:
                        continue

                    # Text search
                    searchable = ""
                    if "desc" in search_fields:
                        searchable += tx.description + " "
                    if "memo" in search_fields:
                        searchable += (split.memo or "") + " "
                    if search_notes:
                        notes = notes_map.get(tx.guid, "")
                        if notes:
                            searchable += notes + " "

                    if not pattern.search(searchable):
                        continue

                    # Deduplication
                    if args.dedupe == "tx" or args.full_tx:
                        if tx.guid in seen_tx_guids:
                            continue
                        seen_tx_guids.add(tx.guid)

                    matching_splits.append((split, tx, acc))

            if not matching_splits:
                return 1  # No matches

            # Format output
            full_account = args.full_account
            rows = _splits_to_rows(
                matching_splits,
                config,
                info,
                args,
                notes_map=notes_map,
                full_account=full_account,
            )

            formatter = OutputFormatter(
                format_type=args.format,
                show_header=not args.no_header,
                include_notes=search_notes,
            )

            if args.full_tx:
                tx_rows = _splits_to_transactions(
                    matching_splits,
                    config,
                    info,
                    args,
                    notes_map=notes_map,
                    full_account=full_account,
                )
                tx_rows = _sort_tx_rows(tx_rows, args.sort, args.reverse)
                if args.offset:
                    tx_rows = tx_rows[args.offset :]
                if args.limit:
                    tx_rows = tx_rows[: args.limit]
                formatter.format_transactions(tx_rows)
            else:
                rows = _sort_rows(rows, args.sort, args.reverse)
                if args.offset:
                    rows = rows[args.offset :]
                if args.limit:
                    rows = rows[: args.limit]
                formatter.format_splits(rows)

            return 0

    except BookOpenError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2


def cmd_ledger(args, config: Config) -> int:
    """Handle the ledger command."""
    after_date, before_date = resolve_date_filters(args)
    amount_range = args.amount if args.amount else (None, None)

    try:
        with open_gnucash_book(config.resolve_book_path()) as (book, info):
            try:
                accounts = get_account_by_pattern(
                    book,
                    args.account_pattern,
                    is_regex=args.account_regex,
                    case_sensitive=False,
                    include_subtree=not args.no_subtree,
                )
            except InvalidPatternError as e:
                print(f"Error: {e}", file=sys.stderr)
                return 2

            if not accounts:
                print(
                    f"No accounts matching: {args.account_pattern}",
                    file=sys.stderr,
                )
                return 1

            splits_data = []
            tx_guids_for_notes = set()

            for acc in accounts:
                for split in acc.splits:
                    tx = split.transaction

                    # Date filter
                    tx_date = tx.post_date
                    if after_date and tx_date < after_date:
                        continue
                    if before_date and tx_date >= before_date:
                        continue

                    # Amount filter
                    split_value = Decimal(str(split.value))
                    if not args.signed:
                        split_value = abs(split_value)
                    min_amt, max_amt = amount_range
                    if min_amt is not None and split_value < min_amt:
                        continue
                    if max_amt is not None and split_value > max_amt:
                        continue

                    splits_data.append((split, tx, acc))
                    tx_guids_for_notes.add(tx.guid)

            if not splits_data:
                return 1

            # Batch fetch notes
            notes_map = get_transaction_notes_batch(
                config.resolve_book_path(),
                list(tx_guids_for_notes),
                info.has_notes_column,
            )

            full_account = args.full_account
            rows = _splits_to_rows(
                splits_data,
                config,
                info,
                args,
                notes_map=notes_map,
                full_account=full_account,
            )
            rows = _sort_rows(rows, args.sort, args.reverse)

            if args.offset:
                rows = rows[args.offset :]
            if args.limit:
                rows = rows[: args.limit]

            formatter = OutputFormatter(
                format_type=args.format,
                show_header=not args.no_header,
            )
            formatter.format_splits(rows)
            return 0

    except BookOpenError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2


def cmd_tx(args, config: Config) -> int:
    """Handle the tx command - show transaction by GUID."""
    try:
        with open_gnucash_book(config.resolve_book_path()) as (book, info):
            tx = get_transaction_by_guid(book, args.guid)

            if tx is None:
                print(f"Transaction not found: {args.guid}", file=sys.stderr)
                return 1

            # Get notes
            notes = get_transaction_notes(
                config.resolve_book_path(), tx.guid, info.has_notes_column
            )

            # Build split rows
            full_account = args.full_account
            split_rows = []
            for split in tx.splits:
                acc = split.account
                split_rows.append(
                    SplitRow(
                        date=tx.post_date,
                        description=tx.description,
                        account=_account_name(acc.fullname, full_account),
                        memo=split.memo,
                        notes=notes,
                        amount=Decimal(str(split.value)),
                        currency=(
                            acc.commodity.mnemonic if acc.commodity else ""
                        ),
                        fx_rate=None,
                        tx_guid=tx.guid,
                        split_guid=split.guid,
                    )
                )

            tx_row = TransactionRow(
                tx_guid=tx.guid,
                date=tx.post_date,
                description=tx.description,
                notes=notes,
                splits=split_rows,
            )

            formatter = OutputFormatter(
                format_type=args.format,
                show_header=not args.no_header,
            )
            formatter.format_transactions([tx_row])
            return 0

    except BookOpenError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2


def cmd_split(args, config: Config) -> int:
    """Handle the split command - show split by GUID."""
    try:
        with open_gnucash_book(config.resolve_book_path()) as (book, info):
            found_split = get_split_by_guid(book, args.guid)

            if found_split is None:
                print(f"Split not found: {args.guid}", file=sys.stderr)
                return 1

            tx = found_split.transaction
            acc = found_split.account
            notes = get_transaction_notes(
                config.resolve_book_path(),
                tx.guid,
                info.has_notes_column,
            )

            full_account = args.full_account
            row = SplitRow(
                date=tx.post_date,
                description=tx.description,
                account=_account_name(acc.fullname, full_account),
                memo=found_split.memo,
                notes=notes,
                amount=Decimal(str(found_split.value)),
                currency=(acc.commodity.mnemonic if acc.commodity else ""),
                fx_rate=None,
                tx_guid=tx.guid,
                split_guid=found_split.guid,
            )

            formatter = OutputFormatter(
                format_type=args.format,
                show_header=not args.no_header,
            )
            formatter.format_splits([row])
            return 0

    except BookOpenError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2


def cmd_doctor(args, config: Config) -> int:
    """Handle the doctor command - print diagnostics."""
    print("gcg diagnostic information")
    print("=" * 40)
    print(f"Version: {__version__}")
    print()

    book_path = config.resolve_book_path()
    print(f"Book path: {book_path}")
    print(f"Book exists: {book_path.exists()}")

    if book_path.exists():
        try:
            with open_gnucash_book(book_path) as (book, info):
                print()
                print("Book info:")
                print(f"  Default currency: {info.default_currency}")
                print(f"  Account count: {info.account_count}")
                print(f"  Transaction count: {info.transaction_count}")
                print(f"  Notes column: {info.has_notes_column}")
                print(f"  Notes in slots: {info.has_slots_notes}")
        except BookOpenError as e:
            print(f"  Error opening: {e}")

    print()
    print("Configuration:")
    print(f"  Base currency: {config.base_currency}")
    print(f"  FX lookback days: {config.fx_lookback_days}")
    print(f"  Output format: {config.output_format}")
    print(f"  Cache path: {config.cache_path}")
    print(f"  Cache enabled: {config.cache_enabled}")

    print()
    print("Environment:")
    print(
        f"  GCG_DEFAULT_BOOK_PATH: "
        f"{os.environ.get('GCG_DEFAULT_BOOK_PATH', '(not set)')}"
    )

    return 0


def cmd_cache(args, config: Config) -> int:
    """Handle the cache command."""
    from gcg.cache import CacheManager

    cache_mgr = CacheManager(config.cache_path, config.resolve_book_path())

    if args.action == "status":
        status = cache_mgr.status()
        print(f"Cache path: {config.cache_path}")
        print(f"Cache exists: {status['exists']}")
        if status["exists"]:
            print(f"Cache size: {status['size_bytes']} bytes")
            print(f"Last modified: {status['modified']}")
            print(f"Split count: {status.get('split_count', 'unknown')}")
        return 0

    elif args.action == "build":
        print(f"Building cache at {config.cache_path}...")
        try:
            with open_gnucash_book(config.resolve_book_path()) as (book, info):
                cache_mgr.build(book, info, force=args.force)
            print("Cache built successfully.")
            return 0
        except BookOpenError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 2

    elif args.action == "drop":
        if cache_mgr.drop():
            print("Cache dropped.")
        else:
            print("No cache to drop.")
        return 0

    return 2


def _splits_to_rows(
    splits_data: list,
    config: Config,
    info,
    args,
    notes_map: Optional[dict[str, str]] = None,
    full_account: bool = False,
) -> list[SplitRow]:
    """Convert split/tx/acc tuples to SplitRow objects."""
    # Batch fetch notes if needed and not already provided
    if notes_map is None and (info.has_notes_column or info.has_slots_notes):
        tx_guids = list({tx.guid for _, tx, _ in splits_data})
        notes_map = get_transaction_notes_batch(
            config.resolve_book_path(),
            tx_guids,
            info.has_notes_column,
        )

    return _shared_splits_to_rows(
        splits_data,
        db_path=config.resolve_book_path(),
        base_currency=(args.base_currency or config.base_currency),
        lookback_days=(args.fx_lookback or config.fx_lookback_days),
        currency_mode=args.currency,
        full_account=full_account,
        signed=args.signed,
        notes_map=notes_map,
        also_original=args.also_original,
    )


def _splits_to_transactions(
    splits_data: list,
    config: Config,
    info,
    args,
    notes_map: Optional[dict[str, str]] = None,
    full_account: bool = False,
) -> list[TransactionRow]:
    """Convert split data to TransactionRow objects (for --full-tx)."""
    # Batch fetch notes if needed and not already provided
    if notes_map is None and (info.has_notes_column or info.has_slots_notes):
        tx_guids = list({tx.guid for _, tx, _ in splits_data})
        notes_map = get_transaction_notes_batch(
            config.resolve_book_path(),
            tx_guids,
            info.has_notes_column,
        )

    return _shared_splits_to_transactions(
        splits_data,
        notes_map=notes_map,
        signed=args.signed,
        full_account=full_account,
        context_mode=args.context,
        select_balanced_fn=_select_balanced_splits,
    )


def _select_balanced_splits(
    all_splits: list,
    matching_guids: set[str],
    signed: bool,
) -> list:
    """
    Select splits to show in balanced context mode.

    Per SPEC §15.2:
    - Include all matching splits
    - Add minimal counter-splits to balance per commodity
    - Sort remaining by absolute value descending, then guid for tie-break
    """

    def _find_balancing_subset(
        splits: list, target: Decimal
    ) -> Optional[list]:
        values = [Decimal(str(s.value)) for s in splits]
        split_count = len(splits)

        for size in range(1, split_count + 1):
            chosen_indexes: list[int] = []

            def backtrack(start: int, remaining: int, total: Decimal) -> bool:
                if remaining == 0:
                    return total == target
                for idx in range(start, split_count - remaining + 1):
                    chosen_indexes.append(idx)
                    if backtrack(
                        idx + 1,
                        remaining - 1,
                        total + values[idx],
                    ):
                        return True
                    chosen_indexes.pop()
                return False

            if backtrack(0, size, Decimal("0")):
                return [splits[i] for i in chosen_indexes]

        return None

    selected = [s for s in all_splits if s.guid in matching_guids]
    remaining = [s for s in all_splits if s.guid not in matching_guids]
    remaining.sort(key=lambda s: (-abs(Decimal(str(s.value))), s.guid))

    balance_by_currency: dict[str, Decimal] = {}
    remaining_by_currency: dict[str, list] = {}

    for s in selected:
        currency = s.account.commodity.mnemonic if s.account.commodity else ""
        value = Decimal(str(s.value))
        balance_by_currency[currency] = (
            balance_by_currency.get(currency, Decimal("0")) + value
        )

    for s in remaining:
        currency = s.account.commodity.mnemonic if s.account.commodity else ""
        remaining_by_currency.setdefault(currency, []).append(s)

    for currency, balance in balance_by_currency.items():
        if balance == Decimal("0"):
            continue
        target = -balance
        subset = _find_balancing_subset(
            remaining_by_currency.get(currency, []), target
        )
        if subset is None:
            print(
                f"Warning: Transaction not perfectly balanced in {currency}, "
                f"showing full context",
                file=sys.stderr,
            )
            return all_splits
        selected.extend(subset)

    return selected


def main(argv: Optional[list[str]] = None) -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args(argv)

    # Load config with CLI overrides
    config = load_config(
        book_path=args.book,
        output_format=args.format,
        show_header=not args.no_header,
    )

    # Handle interactive mode
    if args.interactive or args.command == "repl":
        from gcg.repl import run_repl

        return run_repl(config)

    # Handle commands
    if args.command == "accounts":
        return cmd_accounts(args, config)
    elif args.command == "grep":
        return cmd_grep(args, config)
    elif args.command == "ledger":
        return cmd_ledger(args, config)
    elif args.command == "tx":
        return cmd_tx(args, config)
    elif args.command == "split":
        return cmd_split(args, config)
    elif args.command == "doctor":
        return cmd_doctor(args, config)
    elif args.command == "cache":
        return cmd_cache(args, config)
    elif args.command is None:
        parser.print_help()
        return 0
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
