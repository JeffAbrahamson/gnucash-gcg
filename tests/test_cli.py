"""Tests for CLI argument parsing and date/amount range handling."""

import argparse
import json
from datetime import date
from decimal import Decimal

import pytest

# Skip all tests if piecash is not available (required by gcg.cli)
pytest.importorskip("piecash")

from gcg.cli import main  # noqa: E402


class TestDateParsing:
    """Tests for date parsing functions."""

    def test_parse_date_valid(self):
        """Valid date string should parse correctly."""
        from gcg.cli import parse_date

        result = parse_date("2026-01-15")
        assert result == date(2026, 1, 15)

    def test_parse_date_invalid_format(self):
        """Invalid date format should raise ArgumentTypeError."""
        from gcg.cli import parse_date

        with pytest.raises(argparse.ArgumentTypeError):
            parse_date("01-15-2026")

    def test_parse_date_invalid_date(self):
        """Invalid date value should raise ArgumentTypeError."""
        from gcg.cli import parse_date

        with pytest.raises(argparse.ArgumentTypeError):
            parse_date("2026-13-01")  # Invalid month


class TestDateRangeParsing:
    """Tests for date range parsing."""

    def test_parse_date_range_full(self):
        """Full date range A..B should parse both dates."""
        from gcg.cli import parse_date_range

        start, end = parse_date_range("2026-01-01..2026-01-31")
        assert start == date(2026, 1, 1)
        assert end == date(2026, 1, 31)

    def test_parse_date_range_open_end(self):
        """Open-ended range A.. should have None end."""
        from gcg.cli import parse_date_range

        start, end = parse_date_range("2026-01-01..")
        assert start == date(2026, 1, 1)
        assert end is None

    def test_parse_date_range_open_start(self):
        """Open-start range ..B should have None start."""
        from gcg.cli import parse_date_range

        start, end = parse_date_range("..2026-01-31")
        assert start is None
        assert end == date(2026, 1, 31)

    def test_parse_date_range_no_dots(self):
        """Range without .. should raise error."""
        from gcg.cli import parse_date_range

        with pytest.raises(argparse.ArgumentTypeError):
            parse_date_range("2026-01-01")

    def test_parse_date_range_whitespace(self):
        """Whitespace around dates should be handled."""
        from gcg.cli import parse_date_range

        start, end = parse_date_range(" 2026-01-01 .. 2026-01-31 ")
        assert start == date(2026, 1, 1)
        assert end == date(2026, 1, 31)


class TestAmountRangeParsing:
    """Tests for amount range parsing."""

    def test_parse_amount_range_full(self):
        """Full amount range MIN..MAX should parse both values."""
        from gcg.cli import parse_amount_range

        min_amt, max_amt = parse_amount_range("10..100")
        assert min_amt == Decimal("10")
        assert max_amt == Decimal("100")

    def test_parse_amount_range_open_max(self):
        """Open-max range MIN.. should have None max."""
        from gcg.cli import parse_amount_range

        min_amt, max_amt = parse_amount_range("10..")
        assert min_amt == Decimal("10")
        assert max_amt is None

    def test_parse_amount_range_open_min(self):
        """Open-min range ..MAX should have None min."""
        from gcg.cli import parse_amount_range

        min_amt, max_amt = parse_amount_range("..100")
        assert min_amt is None
        assert max_amt == Decimal("100")

    def test_parse_amount_range_decimals(self):
        """Decimal amounts should parse correctly."""
        from gcg.cli import parse_amount_range

        min_amt, max_amt = parse_amount_range("10.50..99.99")
        assert min_amt == Decimal("10.50")
        assert max_amt == Decimal("99.99")

    def test_parse_amount_range_no_dots(self):
        """Range without .. should raise error."""
        from gcg.cli import parse_amount_range

        with pytest.raises(argparse.ArgumentTypeError):
            parse_amount_range("100")

    def test_parse_amount_range_invalid_number(self):
        """Invalid number should raise error."""
        from gcg.cli import parse_amount_range

        with pytest.raises(argparse.ArgumentTypeError):
            parse_amount_range("abc..100")


class TestResolveDateFilters:
    """Tests for combining date filter arguments."""

    def test_resolve_after_only(self):
        """--after alone should set start date."""
        from gcg.cli import resolve_date_filters

        class Args:
            after = date(2026, 1, 1)
            before = None
            date = None

        after, before = resolve_date_filters(Args())
        assert after == date(2026, 1, 1)
        assert before is None

    def test_resolve_before_only(self):
        """--before alone should set end date."""
        from gcg.cli import resolve_date_filters

        class Args:
            after = None
            before = date(2026, 2, 1)
            date = None

        after, before = resolve_date_filters(Args())
        assert after is None
        assert before == date(2026, 2, 1)

    def test_resolve_date_range(self):
        """--date range should set both with +1 day adjustment."""
        from gcg.cli import resolve_date_filters

        class Args:
            after = None
            before = None
            date = (date(2026, 1, 1), date(2026, 1, 31))

        after, before = resolve_date_filters(Args())
        assert after == date(2026, 1, 1)
        # End should be +1 day because --date is inclusive
        assert before == date(2026, 2, 1)

    def test_resolve_date_range_open_end(self):
        """--date A.. should only set start."""
        from gcg.cli import resolve_date_filters

        class Args:
            after = None
            before = None
            date = (date(2026, 1, 1), None)

        after, before = resolve_date_filters(Args())
        assert after == date(2026, 1, 1)
        assert before is None


class TestParserCreation:
    """Tests for the argument parser."""

    def test_parser_creates(self):
        """Parser should create without errors."""
        from gcg.cli import create_parser

        parser = create_parser()
        assert parser is not None

    def test_parser_accounts_command(self):
        """accounts command should parse correctly."""
        from gcg.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["accounts", "Bank"])
        assert args.command == "accounts"
        assert args.pattern == "Bank"

    def test_parser_accounts_with_options(self):
        """accounts with options should parse correctly."""
        from gcg.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(
            ["accounts", "^Expenses:", "--regex", "--show-guids"]
        )
        assert args.command == "accounts"
        assert args.pattern == "^Expenses:"
        assert args.regex is True
        assert args.show_guids is True

    def test_parser_grep_command(self):
        """grep command should parse correctly."""
        from gcg.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["grep", "amazon"])
        assert args.command == "grep"
        assert args.text == "amazon"

    def test_parser_grep_with_filters(self):
        """grep with date and amount filters should parse."""
        from gcg.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(
            [
                "grep",
                "amazon",
                "--after",
                "2026-01-01",
                "--amount",
                "10..100",
                "--signed",
            ]
        )
        assert args.command == "grep"
        assert args.text == "amazon"
        assert args.after == date(2026, 1, 1)
        assert args.amount == (Decimal("10"), Decimal("100"))
        assert args.signed is True

    def test_parser_ledger_command(self):
        """ledger command should parse correctly."""
        from gcg.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["ledger", "Assets:Bank"])
        assert args.command == "ledger"
        assert args.account_pattern == "Assets:Bank"

    def test_parser_tx_command(self):
        """tx command should parse correctly."""
        from gcg.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["tx", "abc123-guid"])
        assert args.command == "tx"
        assert args.guid == "abc123-guid"

    def test_parser_global_options(self):
        """Global options should parse correctly."""
        from gcg.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(
            [
                "--format",
                "json",
                "--no-header",
                "--sort",
                "amount",
                "--reverse",
                "--limit",
                "10",
                "accounts",
                "Bank",
            ]
        )
        assert args.format == "json"
        assert args.no_header is True
        assert args.sort == "amount"
        assert args.reverse is True
        assert args.limit == 10

    def test_parser_interactive_flag(self):
        """Interactive flag should parse."""
        from gcg.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["-i"])
        assert args.interactive is True

    def test_parser_cache_command(self):
        """cache command should parse correctly."""
        from gcg.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["cache", "build", "--force"])
        assert args.command == "cache"
        assert args.action == "build"
        assert args.force is True


# ===================================================================
# CLI command integration tests via main()
# ===================================================================


def _book(test_book_path):
    return ["--book", str(test_book_path)]


class TestMainNoCommand:
    def test_no_args_shows_help(self, capsys):
        rc = main([])
        assert rc == 0


class TestMainAccounts:
    def test_accounts_all(self, test_book_path, capsys):
        rc = main(_book(test_book_path) + ["accounts"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "Bank" in out

    def test_accounts_pattern(self, test_book_path, capsys):
        rc = main(_book(test_book_path) + ["accounts", "Checking"])
        assert rc == 0
        assert "Checking" in capsys.readouterr().out

    def test_accounts_no_match(self, test_book_path):
        rc = main(_book(test_book_path) + ["accounts", "ZZZNOTEXIST"])
        assert rc == 1

    def test_accounts_regex(self, test_book_path, capsys):
        rc = main(_book(test_book_path) + ["accounts", "Check.*", "--regex"])
        assert rc == 0
        assert "Checking" in capsys.readouterr().out

    def test_accounts_invalid_regex(self, test_book_path):
        rc = main(_book(test_book_path) + ["accounts", "[bad", "--regex"])
        assert rc == 2

    def test_accounts_json(self, test_book_path, capsys):
        rc = main(_book(test_book_path) + ["--format", "json", "accounts"])
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert len(data) > 0

    def test_accounts_csv(self, test_book_path, capsys):
        rc = main(_book(test_book_path) + ["--format", "csv", "accounts"])
        assert rc == 0

    def test_accounts_tree(self, test_book_path, capsys):
        rc = main(
            _book(test_book_path) + ["accounts", "--tree", "--max-depth", "1"]
        )
        assert rc == 0

    def test_accounts_show_guids(self, test_book_path, capsys):
        rc = main(_book(test_book_path) + ["accounts", "--show-guids"])
        assert rc == 0

    def test_accounts_limit_offset(self, test_book_path, capsys):
        rc = main(
            _book(test_book_path)
            + [
                "--format",
                "json",
                "--limit",
                "2",
                "--offset",
                "1",
                "accounts",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert len(data) == 2

    def test_accounts_bad_book(self, tmp_path):
        rc = main(["--book", str(tmp_path / "nope.gnucash"), "accounts"])
        assert rc == 2


class TestMainGrep:
    def test_grep_basic(self, test_book_path, capsys):
        rc = main(_book(test_book_path) + ["grep", "Tesco"])
        assert rc == 0
        assert "Tesco" in capsys.readouterr().out

    def test_grep_no_match(self, test_book_path):
        rc = main(_book(test_book_path) + ["grep", "ZZZNOTEXIST"])
        assert rc == 1

    def test_grep_regex(self, test_book_path, capsys):
        rc = main(_book(test_book_path) + ["grep", "Tes.o", "--regex"])
        assert rc == 0

    def test_grep_invalid_regex(self, test_book_path):
        rc = main(_book(test_book_path) + ["grep", "[bad", "--regex"])
        assert rc == 2

    def test_grep_json(self, test_book_path, capsys):
        rc = main(
            _book(test_book_path) + ["--format", "json", "grep", "Tesco"]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert len(data) > 0

    def test_grep_with_account(self, test_book_path, capsys):
        rc = main(
            _book(test_book_path) + ["grep", "Tesco", "--account", "Groceries"]
        )
        assert rc == 0

    def test_grep_with_dates(self, test_book_path, capsys):
        rc = main(
            _book(test_book_path)
            + [
                "grep",
                "Tesco",
                "--after",
                "2026-01-01",
                "--before",
                "2026-02-01",
            ]
        )
        assert rc == 0

    def test_grep_with_amount(self, test_book_path, capsys):
        rc = main(
            _book(test_book_path) + ["grep", "Tesco", "--amount", "40..50"]
        )
        assert rc == 0

    def test_grep_full_tx(self, test_book_path, capsys):
        rc = main(_book(test_book_path) + ["grep", "Tesco", "--full-tx"])
        assert rc == 0
        assert "Tesco" in capsys.readouterr().out

    def test_grep_limit_offset(self, test_book_path, capsys):
        rc = main(
            _book(test_book_path)
            + [
                "--format",
                "json",
                "--limit",
                "1",
                "--offset",
                "0",
                "grep",
                "Tesco",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert len(data) == 1

    def test_grep_sort_reverse(self, test_book_path, capsys):
        rc = main(
            _book(test_book_path)
            + ["--sort", "amount", "--reverse", "grep", ""]
        )
        assert rc == 0

    def test_grep_bad_book(self, tmp_path):
        rc = main(["--book", str(tmp_path / "nope.gnucash"), "grep", "x"])
        assert rc == 2

    def test_grep_dedupe_tx(self, test_book_path, capsys):
        rc = main(_book(test_book_path) + ["grep", "Tesco", "--dedupe", "tx"])
        assert rc == 0


class TestMainLedger:
    def test_ledger_basic(self, test_book_path, capsys):
        rc = main(_book(test_book_path) + ["ledger", "Checking"])
        assert rc == 0
        assert len(capsys.readouterr().out.strip()) > 0

    def test_ledger_no_match(self, test_book_path):
        rc = main(_book(test_book_path) + ["ledger", "ZZZNOTEXIST"])
        assert rc == 1

    def test_ledger_with_dates(self, test_book_path, capsys):
        rc = main(
            _book(test_book_path)
            + [
                "ledger",
                "Checking",
                "--after",
                "2026-01-01",
                "--before",
                "2026-02-01",
            ]
        )
        assert rc == 0

    def test_ledger_with_amount(self, test_book_path, capsys):
        rc = main(
            _book(test_book_path) + ["ledger", "Checking", "--amount", "100.."]
        )
        assert rc == 0

    def test_ledger_no_splits(self, test_book_path):
        rc = main(
            _book(test_book_path)
            + ["ledger", "Checking", "--after", "2099-01-01"]
        )
        assert rc == 1

    def test_ledger_json(self, test_book_path, capsys):
        rc = main(
            _book(test_book_path) + ["--format", "json", "ledger", "Checking"]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert len(data) > 0

    def test_ledger_limit_offset(self, test_book_path, capsys):
        rc = main(
            _book(test_book_path)
            + [
                "--format",
                "json",
                "--limit",
                "1",
                "--offset",
                "1",
                "ledger",
                "Checking",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert len(data) == 1

    def test_ledger_invalid_regex(self, test_book_path):
        rc = main(
            _book(test_book_path) + ["ledger", "[bad", "--account-regex"]
        )
        assert rc == 2

    def test_ledger_bad_book(self, tmp_path):
        rc = main(
            [
                "--book",
                str(tmp_path / "nope.gnucash"),
                "ledger",
                "X",
            ]
        )
        assert rc == 2


class TestMainTx:
    def test_tx_not_found(self, test_book_path):
        rc = main(_book(test_book_path) + ["tx", "nonexistent-guid"])
        assert rc == 1

    def test_tx_found(self, test_book_path, capsys):
        """Look up a real GUID from the book."""
        from gcg.book import open_gnucash_book

        with open_gnucash_book(test_book_path) as (book, _):
            guid = list(book.transactions)[0].guid
        rc = main(_book(test_book_path) + ["tx", guid])
        assert rc == 0
        assert len(capsys.readouterr().out.strip()) > 0

    def test_tx_bad_book(self, tmp_path):
        rc = main(
            [
                "--book",
                str(tmp_path / "nope.gnucash"),
                "tx",
                "abc",
            ]
        )
        assert rc == 2


class TestMainSplit:
    def test_split_not_found(self, test_book_path):
        rc = main(_book(test_book_path) + ["split", "nonexistent-guid"])
        assert rc == 1

    def test_split_found(self, test_book_path, capsys):
        from gcg.book import open_gnucash_book

        with open_gnucash_book(test_book_path) as (book, _):
            for acc in book.accounts:
                if acc.splits:
                    guid = acc.splits[0].guid
                    break
        rc = main(_book(test_book_path) + ["split", guid])
        assert rc == 0
        assert len(capsys.readouterr().out.strip()) > 0

    def test_split_bad_book(self, tmp_path):
        rc = main(
            [
                "--book",
                str(tmp_path / "nope.gnucash"),
                "split",
                "abc",
            ]
        )
        assert rc == 2


class TestMainDoctor:
    def test_doctor(self, test_book_path, capsys):
        rc = main(_book(test_book_path) + ["doctor"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "diagnostic" in out.lower()


class TestMainCache:
    def test_cache_status(self, test_book_path, capsys):
        rc = main(_book(test_book_path) + ["cache", "status"])
        assert rc == 0
        assert "Cache" in capsys.readouterr().out

    def test_cache_build_and_drop(self, test_book_path, tmp_path, capsys):
        cache_file = tmp_path / "test_cache.sqlite"
        # Patch cache_path via env or use config; simplest is to test
        # via the cmd_cache function directly
        from gcg.cli import cmd_cache
        from gcg.config import Config

        config = Config(book_path=test_book_path, cache_path=cache_file)

        class Args:
            action = "build"
            force = False

        rc = cmd_cache(Args(), config)
        assert rc == 0
        assert cache_file.exists()
        capsys.readouterr()

        # Drop
        Args.action = "drop"
        rc = cmd_cache(Args(), config)
        assert rc == 0
        assert not cache_file.exists()

    def test_cache_drop_no_cache(self, test_book_path, tmp_path, capsys):
        from gcg.cli import cmd_cache
        from gcg.config import Config

        config = Config(
            book_path=test_book_path,
            cache_path=tmp_path / "nonexistent.sqlite",
        )

        class Args:
            action = "drop"
            force = False

        rc = cmd_cache(Args(), config)
        assert rc == 0
        assert "No cache to drop" in capsys.readouterr().out
