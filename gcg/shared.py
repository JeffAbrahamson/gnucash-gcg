"""
Shared utility functions used by both cli.py and repl.py.

Extracted to avoid duplication of core logic like account name
formatting, split-to-row conversion, sorting, and tree pruning.
"""

from decimal import Decimal
from typing import Optional

from gcg.currency import (
    CurrencyConverter,
    determine_display_currency,
    get_account_currencies,
)
from gcg.output import SplitRow, TransactionRow


def account_name(fullname: str, full_account: bool) -> str:
    """Return account name - full path or just final component."""
    if full_account:
        return fullname
    return fullname.rsplit(":", 1)[-1]


def sort_rows(
    rows: list[SplitRow], sort_key: str, reverse: bool
) -> list[SplitRow]:
    """Sort split rows by the specified key."""
    key_map = {
        "date": lambda r: r.date,
        "amount": lambda r: r.amount,
        "account": lambda r: r.account,
        "description": lambda r: r.description,
    }
    key_fn = key_map.get(sort_key, key_map["date"])
    return sorted(rows, key=key_fn, reverse=reverse)


def sort_tx_rows(
    rows: list[TransactionRow], sort_key: str, reverse: bool
) -> list[TransactionRow]:
    """Sort transaction rows by the specified key."""
    key_map = {
        "date": lambda r: r.date,
        "amount": lambda r: (
            max(abs(s.amount) for s in r.splits) if r.splits else 0
        ),
        "account": lambda r: (r.splits[0].account if r.splits else ""),
        "description": lambda r: r.description,
    }
    key_fn = key_map.get(sort_key, key_map["date"])
    return sorted(rows, key=key_fn, reverse=reverse)


def prune_to_matching_paths(matching_accounts: list, book) -> list:
    """
    Prune account tree to show paths to matching accounts.

    Shows the tree from root down to matching paths, plus full
    subtrees below any matching accounts.
    """
    matching_set = set(matching_accounts)
    result_set = set(matching_accounts)

    for acc in matching_accounts:
        parent = acc.parent
        while parent is not None:
            if parent.type not in ("ROOT", "TRADING"):
                result_set.add(parent)
            parent = parent.parent

    all_accounts = [
        a for a in book.accounts if a.type not in ("ROOT", "TRADING")
    ]
    for acc in all_accounts:
        parent = acc.parent
        while parent is not None:
            if parent in matching_set:
                result_set.add(acc)
                break
            parent = parent.parent

    return list(result_set)


def splits_to_rows(
    splits_data: list,
    db_path,
    base_currency: str,
    lookback_days: int,
    currency_mode: str,
    full_account: bool,
    signed: bool,
    notes_map: Optional[dict[str, str]] = None,
    also_original: bool = False,
) -> list[SplitRow]:
    """Convert split/tx/acc tuples to SplitRow objects."""
    if notes_map is None:
        notes_map = {}

    rows = []
    converter = CurrencyConverter(
        db_path,
        base_currency=base_currency,
        lookback_days=lookback_days,
    )

    account_currencies = get_account_currencies(
        [acc for _, _, acc in splits_data]
    )
    target_currency = determine_display_currency(
        currency_mode,
        [s for s, _, _ in splits_data],
        account_currencies,
        base_currency,
    )

    for split, tx, acc in splits_data:
        split_value = Decimal(str(split.value))
        if not signed:
            split_value = abs(split_value)

        split_currency = acc.commodity.mnemonic if acc.commodity else "???"
        if target_currency and target_currency != split_currency:
            result = converter.convert(
                split_value,
                split_currency,
                target_currency,
                tx.post_date,
            )
            display_amount = result.amount
            display_currency = result.currency
            fx_rate = result.fx_rate if result.converted else None
        else:
            display_amount = split_value
            display_currency = split_currency
            fx_rate = None

        notes = notes_map.get(tx.guid)

        row = SplitRow(
            date=tx.post_date,
            description=tx.description,
            account=account_name(acc.fullname, full_account),
            memo=split.memo,
            notes=notes,
            amount=display_amount,
            currency=display_currency,
            fx_rate=fx_rate,
            tx_guid=tx.guid,
            split_guid=split.guid,
        )

        if also_original and fx_rate:
            row.amount_orig = split_value
            row.currency_orig = split_currency

        rows.append(row)

    return rows


def splits_to_transactions(
    splits_data: list,
    notes_map: Optional[dict[str, str]],
    signed: bool,
    full_account: bool,
    context_mode: str = "full",
    select_balanced_fn=None,
) -> list[TransactionRow]:
    """Convert split data to TransactionRow objects.

    Args:
        splits_data: List of (split, tx, acc) tuples.
        notes_map: Map of tx_guid -> notes text.
        signed: Whether to use signed amounts.
        full_account: Whether to show full account paths.
        context_mode: "full" or "balanced".
        select_balanced_fn: Function implementing balanced
            context selection. Required if context_mode is
            "balanced".
    """
    if notes_map is None:
        notes_map = {}

    tx_map: dict = {}
    for split, tx, acc in splits_data:
        if tx.guid not in tx_map:
            tx_map[tx.guid] = {
                "tx": tx,
                "notes": notes_map.get(tx.guid),
                "all_splits": [],
                "matching_splits": set(),
            }

        tx_map[tx.guid]["matching_splits"].add(split.guid)

        for s in tx.splits:
            tx_map[tx.guid]["all_splits"].append(s)

    rows = []
    for guid, data in tx_map.items():
        tx = data["tx"]

        # Dedupe all_splits by guid
        seen_guids: set = set()
        unique_all_splits = []
        for s in data["all_splits"]:
            if s.guid not in seen_guids:
                seen_guids.add(s.guid)
                unique_all_splits.append(s)

        if context_mode == "balanced" and select_balanced_fn is not None:
            selected_splits = select_balanced_fn(
                unique_all_splits,
                data["matching_splits"],
                signed,
            )
        else:
            selected_splits = unique_all_splits

        split_rows = []
        for s in selected_splits:
            split_acc = s.account
            split_value = Decimal(str(s.value))
            if not signed:
                split_value = abs(split_value)

            split_rows.append(
                SplitRow(
                    date=tx.post_date,
                    description=tx.description,
                    account=account_name(split_acc.fullname, full_account),
                    memo=s.memo,
                    notes=data["notes"],
                    amount=split_value,
                    currency=(
                        split_acc.commodity.mnemonic
                        if split_acc.commodity
                        else ""
                    ),
                    fx_rate=None,
                    tx_guid=tx.guid,
                    split_guid=s.guid,
                )
            )

        rows.append(
            TransactionRow(
                tx_guid=guid,
                date=tx.post_date,
                description=tx.description,
                notes=data["notes"],
                splits=split_rows,
            )
        )

    return rows
