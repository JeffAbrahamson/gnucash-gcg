"""Tests for gcg REPL module."""

from datetime import date
from decimal import Decimal

import pytest

from gcg.config import Config
from gcg.output import SplitRow
from gcg.repl import ReplSession, _account_name

# ---------------------------------------------------------------------------
# Helper: create a minimal Config (no real book needed for unit tests)
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_history(tmp_path):
    """Return a temporary history file path."""
    return tmp_path / "gcg" / "history"


@pytest.fixture
def config(tmp_history):
    """Config with a temporary history path and no book."""
    return Config(history_path=tmp_history)


@pytest.fixture
def session(config):
    """A fresh ReplSession with no book open."""
    return ReplSession(config)


@pytest.fixture
def session_with_book(test_book_path, tmp_history):
    """A ReplSession with the test book already open."""
    cfg = Config(book_path=test_book_path, history_path=tmp_history)
    sess = ReplSession(cfg)
    sess.open_book(str(test_book_path))
    yield sess
    sess.close_book()


# ===================================================================
# _account_name
# ===================================================================


class TestAccountName:
    def test_full_account(self):
        assert _account_name("Assets:Bank:Checking", True) == (
            "Assets:Bank:Checking"
        )

    def test_short_account(self):
        assert _account_name("Assets:Bank:Checking", False) == "Checking"

    def test_single_component(self):
        assert _account_name("Assets", False) == "Assets"
        assert _account_name("Assets", True) == "Assets"


# ===================================================================
# ReplSession.__init__
# ===================================================================


class TestReplSessionInit:
    def test_defaults(self, session, config):
        assert session.book is None
        assert session.book_info is None
        assert session.book_path is None
        assert session.running is True
        assert session.output_format == config.output_format
        assert session.currency_mode == config.currency_mode
        assert session.base_currency == config.base_currency
        assert session.full_account is False

    def test_history_path_from_config(self, tmp_history):
        cfg = Config(history_path=tmp_history)
        sess = ReplSession(cfg)
        assert sess.history_path == tmp_history


# ===================================================================
# setup_readline / save_history
# ===================================================================


class TestReadlineHistory:
    def test_setup_readline_creates_directory(self, session):
        assert not session.history_path.parent.exists()
        session.setup_readline()
        assert session.history_path.parent.exists()

    def test_save_history_no_error(self, session):
        session.setup_readline()
        # Should not raise even on first run (no existing history)
        session.save_history()

    def test_setup_readline_loads_existing_history(self, session):
        session.history_path.parent.mkdir(parents=True, exist_ok=True)
        session.history_path.write_text("")
        session.setup_readline()  # should not raise


# ===================================================================
# run_command — dispatch
# ===================================================================


class TestRunCommand:
    def test_empty_line(self, session, capsys):
        session.run_command("")
        assert capsys.readouterr().out == ""

    def test_comment_line(self, session, capsys):
        session.run_command("# this is a comment")
        assert capsys.readouterr().out == ""

    def test_whitespace_only(self, session, capsys):
        session.run_command("   ")
        assert capsys.readouterr().out == ""

    def test_quit(self, session):
        session.run_command("quit")
        assert session.running is False

    def test_exit(self, session):
        session.run_command("exit")
        assert session.running is False

    def test_help(self, session, capsys):
        session.run_command("help")
        out = capsys.readouterr().out
        assert "gcg REPL Commands:" in out

    def test_unknown_command(self, session_with_book, capsys):
        session_with_book.run_command("foobar")
        err = capsys.readouterr().err
        assert "Unknown command: foobar" in err

    def test_command_requires_book(self, session, capsys):
        session.run_command("accounts")
        err = capsys.readouterr().err
        assert "No book open" in err

    def test_parse_error(self, session, capsys):
        # Unterminated quote triggers shlex parse error
        session.run_command('"unterminated')
        err = capsys.readouterr().err
        assert "Parse error" in err

    def test_case_insensitive_command(self, session):
        session.run_command("QUIT")
        assert session.running is False


# ===================================================================
# cmd_set
# ===================================================================


class TestCmdSet:
    def test_show_current_settings(self, session, capsys):
        session.cmd_set([])
        out = capsys.readouterr().out
        assert "format:" in out
        assert "currency:" in out
        assert "base-currency:" in out
        assert "full-account:" in out

    # -- format --
    def test_set_format_json(self, session, capsys):
        session.cmd_set(["format", "json"])
        assert session.output_format == "json"
        assert "json" in capsys.readouterr().out

    def test_set_format_csv(self, session, capsys):
        session.cmd_set(["format", "csv"])
        assert session.output_format == "csv"

    def test_set_format_table(self, session, capsys):
        session.output_format = "json"
        session.cmd_set(["format", "table"])
        assert session.output_format == "table"

    def test_set_format_invalid(self, session, capsys):
        session.cmd_set(["format", "xml"])
        out = capsys.readouterr().out
        assert "Invalid format" in out
        assert session.output_format == "table"  # unchanged

    # -- currency --
    def test_set_currency_base(self, session, capsys):
        session.cmd_set(["currency", "base"])
        assert session.currency_mode == "base"
        assert "base" in capsys.readouterr().out

    def test_set_currency_split(self, session):
        session.cmd_set(["currency", "split"])
        assert session.currency_mode == "split"

    def test_set_currency_account(self, session):
        session.cmd_set(["currency", "account"])
        assert session.currency_mode == "account"

    def test_set_currency_auto(self, session):
        session.currency_mode = "base"
        session.cmd_set(["currency", "auto"])
        assert session.currency_mode == "auto"

    def test_set_currency_invalid(self, session, capsys):
        session.cmd_set(["currency", "magic"])
        out = capsys.readouterr().out
        assert "Invalid mode" in out

    # -- base-currency --
    def test_set_base_currency(self, session, capsys):
        session.cmd_set(["base-currency", "usd"])
        assert session.base_currency == "USD"
        assert "USD" in capsys.readouterr().out

    # -- full-account --
    def test_set_full_account_on(self, session, capsys):
        session.cmd_set(["full-account", "on"])
        assert session.full_account is True
        assert "Full account" in capsys.readouterr().out

    def test_set_full_account_true(self, session):
        session.cmd_set(["full-account", "true"])
        assert session.full_account is True

    def test_set_full_account_yes(self, session):
        session.cmd_set(["full-account", "yes"])
        assert session.full_account is True

    def test_set_full_account_1(self, session):
        session.cmd_set(["full-account", "1"])
        assert session.full_account is True

    def test_set_full_account_off(self, session, capsys):
        session.full_account = True
        session.cmd_set(["full-account", "off"])
        assert session.full_account is False
        assert "Short account" in capsys.readouterr().out

    def test_set_full_account_false(self, session):
        session.full_account = True
        session.cmd_set(["full-account", "false"])
        assert session.full_account is False

    def test_set_full_account_no(self, session):
        session.full_account = True
        session.cmd_set(["full-account", "no"])
        assert session.full_account is False

    def test_set_full_account_0(self, session):
        session.full_account = True
        session.cmd_set(["full-account", "0"])
        assert session.full_account is False

    def test_set_full_account_invalid(self, session, capsys):
        session.cmd_set(["full-account", "maybe"])
        out = capsys.readouterr().out
        assert "Invalid value" in out

    # -- unknown setting --
    def test_set_unknown_setting(self, session, capsys):
        session.cmd_set(["nonexistent", "val"])
        out = capsys.readouterr().out
        assert "Unknown setting" in out


# ===================================================================
# cmd_help
# ===================================================================


class TestCmdHelp:
    def test_help_output(self, session, capsys):
        session.cmd_help([])
        out = capsys.readouterr().out
        assert "open" in out
        assert "accounts" in out
        assert "grep" in out
        assert "ledger" in out
        assert "tx" in out
        assert "split" in out
        assert "set" in out
        assert "quit" in out


# ===================================================================
# open_book / close_book
# ===================================================================


class TestOpenCloseBook:
    def test_open_book_success(self, test_book_path, session, capsys):
        result = session.open_book(str(test_book_path))
        assert result is True
        assert session.book is not None
        assert session.book_info is not None
        out = capsys.readouterr().out
        assert "Opened:" in out
        assert "Accounts:" in out
        session.close_book()

    def test_open_book_nonexistent(self, session, capsys):
        result = session.open_book("/nonexistent/path/book.gnucash")
        assert result is False
        assert session.book is None
        err = capsys.readouterr().err
        assert "Error" in err

    def test_close_book_when_none(self, session):
        # Should not raise
        session.close_book()
        assert session.book is None

    def test_open_replaces_previous(self, test_book_path, session):
        session.open_book(str(test_book_path))
        first_book = session.book
        assert first_book is not None
        # Open again — should close previous
        session.open_book(str(test_book_path))
        assert session.book is not None
        session.close_book()


# ===================================================================
# _sort_rows
# ===================================================================


def _make_split_row(**overrides):
    defaults = dict(
        date=date(2026, 1, 1),
        description="desc",
        account="Acct",
        memo=None,
        notes=None,
        amount=Decimal("10"),
        currency="EUR",
        fx_rate=None,
        tx_guid="g1",
        split_guid="s1",
    )
    defaults.update(overrides)
    return SplitRow(**defaults)


class TestSortRows:
    def test_sort_by_date(self, session):
        rows = [
            _make_split_row(date=date(2026, 1, 3)),
            _make_split_row(date=date(2026, 1, 1)),
            _make_split_row(date=date(2026, 1, 2)),
        ]
        result = session._sort_rows(rows, "date", False)
        assert [r.date.day for r in result] == [1, 2, 3]

    def test_sort_by_date_reverse(self, session):
        rows = [
            _make_split_row(date=date(2026, 1, 1)),
            _make_split_row(date=date(2026, 1, 3)),
        ]
        result = session._sort_rows(rows, "date", True)
        assert result[0].date.day == 3

    def test_sort_by_amount(self, session):
        rows = [
            _make_split_row(amount=Decimal("30")),
            _make_split_row(amount=Decimal("10")),
            _make_split_row(amount=Decimal("20")),
        ]
        result = session._sort_rows(rows, "amount", False)
        assert [r.amount for r in result] == [
            Decimal("10"),
            Decimal("20"),
            Decimal("30"),
        ]

    def test_sort_by_account(self, session):
        rows = [
            _make_split_row(account="C"),
            _make_split_row(account="A"),
            _make_split_row(account="B"),
        ]
        result = session._sort_rows(rows, "account", False)
        assert [r.account for r in result] == ["A", "B", "C"]

    def test_sort_by_description(self, session):
        rows = [
            _make_split_row(description="Zebra"),
            _make_split_row(description="Apple"),
        ]
        result = session._sort_rows(rows, "description", False)
        assert result[0].description == "Apple"

    def test_sort_unknown_key_falls_back_to_date(self, session):
        rows = [
            _make_split_row(date=date(2026, 1, 2)),
            _make_split_row(date=date(2026, 1, 1)),
        ]
        result = session._sort_rows(rows, "nonexistent", False)
        assert result[0].date.day == 1


# ===================================================================
# Commands that require an open book
# ===================================================================


class TestCmdAccounts:
    def test_accounts_no_pattern(self, session_with_book, capsys):
        session_with_book.cmd_accounts([])
        out = capsys.readouterr().out
        # Should list accounts
        assert "Bank" in out or "Assets" in out

    def test_accounts_with_pattern(self, session_with_book, capsys):
        session_with_book.cmd_accounts(["Bank"])
        out = capsys.readouterr().out
        assert "Bank" in out

    def test_accounts_no_match(self, session_with_book, capsys):
        session_with_book.cmd_accounts(["ZZZNOTEXIST"])
        out = capsys.readouterr().out
        assert "No matching accounts" in out

    def test_accounts_regex(self, session_with_book, capsys):
        session_with_book.cmd_accounts(["Check.*", "--regex"])
        out = capsys.readouterr().out
        assert "Checking" in out

    def test_accounts_json(self, session_with_book, capsys):
        session_with_book.output_format = "json"
        session_with_book.cmd_accounts([])
        out = capsys.readouterr().out
        assert "[" in out  # JSON array

    def test_accounts_show_guids(self, session_with_book, capsys):
        session_with_book.cmd_accounts(["Checking", "--show-guids"])
        out = capsys.readouterr().out
        assert len(out.strip()) > 0

    def test_accounts_limit(self, session_with_book, capsys):
        session_with_book.output_format = "json"
        session_with_book.cmd_accounts(["--limit", "1"])
        out = capsys.readouterr().out
        import json

        data = json.loads(out)
        assert len(data) == 1

    def test_accounts_tree(self, session_with_book, capsys):
        session_with_book.cmd_accounts(["--tree"])
        out = capsys.readouterr().out
        assert len(out.strip()) > 0

    def test_accounts_invalid_regex(self, session_with_book, capsys):
        session_with_book.cmd_accounts(["[invalid", "--regex"])
        err = capsys.readouterr().err
        assert "Error" in err


class TestCmdGrep:
    def test_grep_no_args(self, session_with_book, capsys):
        session_with_book.cmd_grep([])
        err = capsys.readouterr().err
        assert "Usage" in err

    def test_grep_finds_match(self, session_with_book, capsys):
        session_with_book.cmd_grep(["Tesco"])
        out = capsys.readouterr().out
        assert "Tesco" in out

    def test_grep_no_match(self, session_with_book, capsys):
        session_with_book.cmd_grep(["ZZZNOTEXIST"])
        out = capsys.readouterr().out
        assert "No matches" in out

    def test_grep_case_insensitive(self, session_with_book, capsys):
        session_with_book.cmd_grep(["tesco"])
        out = capsys.readouterr().out
        assert "Tesco" in out or "tesco" in out.lower()

    def test_grep_with_after(self, session_with_book, capsys):
        session_with_book.cmd_grep(["salary", "--after", "2026-01-14"])
        out = capsys.readouterr().out
        assert "salary" in out.lower()

    def test_grep_with_before(self, session_with_book, capsys):
        session_with_book.cmd_grep(["Tesco", "--before", "2026-01-06"])
        out = capsys.readouterr().out
        assert "Tesco" in out

    def test_grep_with_amount_range(self, session_with_book, capsys):
        session_with_book.cmd_grep(["Tesco", "--amount", "40..50"])
        out = capsys.readouterr().out
        assert "Tesco" in out

    def test_grep_invalid_date(self, session_with_book, capsys):
        session_with_book.cmd_grep(["test", "--after", "not-a-date"])
        err = capsys.readouterr().err
        assert "Invalid date" in err

    def test_grep_invalid_before_date(self, session_with_book, capsys):
        session_with_book.cmd_grep(["test", "--before", "bad"])
        err = capsys.readouterr().err
        assert "Invalid date" in err

    def test_grep_regex(self, session_with_book, capsys):
        session_with_book.cmd_grep(["Tes.o", "--regex"])
        out = capsys.readouterr().out
        assert "Tesco" in out

    def test_grep_invalid_regex(self, session_with_book, capsys):
        session_with_book.cmd_grep(["[bad", "--regex"])
        err = capsys.readouterr().err
        assert "Invalid regex" in err

    def test_grep_with_account_filter(self, session_with_book, capsys):
        session_with_book.cmd_grep(["Tesco", "--account", "Groceries"])
        out = capsys.readouterr().out
        assert "Tesco" in out

    def test_grep_json_output(self, session_with_book, capsys):
        session_with_book.output_format = "json"
        session_with_book.cmd_grep(["salary"])
        out = capsys.readouterr().out
        assert "[" in out

    def test_grep_with_limit(self, session_with_book, capsys):
        session_with_book.output_format = "json"
        session_with_book.cmd_grep(["", "--limit", "1"])
        out = capsys.readouterr().out
        import json

        data = json.loads(out)
        assert len(data) == 1

    def test_grep_with_sort_amount(self, session_with_book, capsys):
        session_with_book.cmd_grep(["", "--sort", "amount"])
        out = capsys.readouterr().out
        assert len(out.strip()) > 0

    def test_grep_with_reverse(self, session_with_book, capsys):
        session_with_book.cmd_grep(["", "--reverse"])
        out = capsys.readouterr().out
        assert len(out.strip()) > 0

    def test_grep_full_tx(self, session_with_book, capsys):
        session_with_book.cmd_grep(["Tesco", "--full-tx"])
        out = capsys.readouterr().out
        assert "Tesco" in out


class TestCmdLedger:
    def test_ledger_no_args(self, session_with_book, capsys):
        session_with_book.cmd_ledger([])
        err = capsys.readouterr().err
        assert "Usage" in err

    def test_ledger_basic(self, session_with_book, capsys):
        session_with_book.cmd_ledger(["Checking"])
        out = capsys.readouterr().out
        assert len(out.strip()) > 0

    def test_ledger_no_match(self, session_with_book, capsys):
        session_with_book.cmd_ledger(["ZZZNOTEXIST"])
        out = capsys.readouterr().out
        assert "No accounts matching" in out

    def test_ledger_with_after(self, session_with_book, capsys):
        session_with_book.cmd_ledger(["Checking", "--after", "2026-01-20"])
        out = capsys.readouterr().out
        assert len(out.strip()) > 0

    def test_ledger_with_amount(self, session_with_book, capsys):
        session_with_book.cmd_ledger(["Checking", "--amount", "100.."])
        out = capsys.readouterr().out
        assert len(out.strip()) > 0

    def test_ledger_invalid_date(self, session_with_book, capsys):
        session_with_book.cmd_ledger(["Checking", "--after", "nope"])
        err = capsys.readouterr().err
        assert "Invalid date" in err

    def test_ledger_invalid_before_date(self, session_with_book, capsys):
        session_with_book.cmd_ledger(["Checking", "--before", "nope"])
        err = capsys.readouterr().err
        assert "Invalid date" in err

    def test_ledger_no_matching_splits(self, session_with_book, capsys):
        session_with_book.cmd_ledger(["Checking", "--after", "2099-01-01"])
        out = capsys.readouterr().out
        assert "No matching splits" in out

    def test_ledger_json(self, session_with_book, capsys):
        session_with_book.output_format = "json"
        session_with_book.cmd_ledger(["Checking"])
        out = capsys.readouterr().out
        assert "[" in out

    def test_ledger_with_sort_reverse(self, session_with_book, capsys):
        session_with_book.cmd_ledger(
            ["Checking", "--sort", "amount", "--reverse"]
        )
        out = capsys.readouterr().out
        assert len(out.strip()) > 0

    def test_ledger_invalid_regex(self, session_with_book, capsys):
        session_with_book.cmd_ledger(["[invalid", "--account-regex"])
        err = capsys.readouterr().err
        assert "Error" in err


class TestCmdTx:
    def test_tx_no_args(self, session_with_book, capsys):
        session_with_book.cmd_tx([])
        err = capsys.readouterr().err
        assert "Usage" in err

    def test_tx_not_found(self, session_with_book, capsys):
        session_with_book.cmd_tx(["nonexistent-guid"])
        err = capsys.readouterr().err
        assert "not found" in err

    def test_tx_found(self, session_with_book, capsys):
        # Get a real GUID from the book
        tx = list(session_with_book.book.transactions)[0]
        session_with_book.cmd_tx([tx.guid])
        out = capsys.readouterr().out
        assert len(out.strip()) > 0


class TestCmdSplit:
    def test_split_no_args(self, session_with_book, capsys):
        session_with_book.cmd_split([])
        err = capsys.readouterr().err
        assert "Usage" in err

    def test_split_not_found(self, session_with_book, capsys):
        session_with_book.cmd_split(["nonexistent-guid"])
        err = capsys.readouterr().err
        assert "not found" in err

    def test_split_found(self, session_with_book, capsys):
        # Get a real split GUID from the book
        for acc in session_with_book.book.accounts:
            if acc.splits:
                guid = acc.splits[0].guid
                break
        session_with_book.cmd_split([guid])
        out = capsys.readouterr().out
        assert len(out.strip()) > 0


# ===================================================================
# run_command integration with book commands
# ===================================================================


class TestRunCommandWithBook:
    def test_dispatch_accounts(self, session_with_book, capsys):
        session_with_book.run_command("accounts Bank")
        out = capsys.readouterr().out
        assert "Bank" in out

    def test_dispatch_grep(self, session_with_book, capsys):
        session_with_book.run_command("grep Tesco")
        out = capsys.readouterr().out
        assert "Tesco" in out

    def test_dispatch_ledger(self, session_with_book, capsys):
        session_with_book.run_command("ledger Checking")
        out = capsys.readouterr().out
        assert len(out.strip()) > 0

    def test_dispatch_set_via_run_command(self, session_with_book):
        session_with_book.run_command("set format json")
        assert session_with_book.output_format == "json"

    def test_dispatch_open_via_run_command(
        self, session_with_book, test_book_path, capsys
    ):
        session_with_book.run_command(f"open {test_book_path}")
        out = capsys.readouterr().out
        assert "Opened:" in out

    def test_dispatch_tx(self, session_with_book, capsys):
        guid = list(session_with_book.book.transactions)[0].guid
        session_with_book.run_command(f"tx {guid}")
        out = capsys.readouterr().out
        assert len(out.strip()) > 0

    def test_dispatch_split(self, session_with_book, capsys):
        for acc in session_with_book.book.accounts:
            if acc.splits:
                guid = acc.splits[0].guid
                break
        session_with_book.run_command(f"split {guid}")
        out = capsys.readouterr().out
        assert len(out.strip()) > 0

    def test_open_no_path_uses_config(
        self, test_book_path, tmp_history, capsys
    ):
        cfg = Config(book_path=test_book_path, history_path=tmp_history)
        sess = ReplSession(cfg)
        sess.run_command("open")
        out = capsys.readouterr().out
        assert "Opened:" in out
        sess.close_book()


# ===================================================================
# Accounts: tree-prune, max-depth, offset
# ===================================================================


class TestAccountsExtended:
    def test_accounts_tree_prune(self, session_with_book, capsys):
        session_with_book.cmd_accounts(["Groceries", "--tree-prune"])
        out = capsys.readouterr().out
        assert "Expenses" in out or "Food" in out

    def test_accounts_max_depth(self, session_with_book, capsys):
        session_with_book.cmd_accounts(["--tree", "--max-depth", "0"])
        out = capsys.readouterr().out
        assert len(out.strip()) > 0

    def test_accounts_offset(self, session_with_book, capsys):
        session_with_book.output_format = "json"
        session_with_book.cmd_accounts(["--offset", "1", "--limit", "2"])
        out = capsys.readouterr().out
        import json

        data = json.loads(out)
        assert len(data) == 2


# ===================================================================
# Grep: extended filter coverage
# ===================================================================


class TestGrepExtended:
    def test_grep_account_filter(self, session_with_book, capsys):
        session_with_book.cmd_grep(["Tesco", "--account", "Groceries"])
        out = capsys.readouterr().out
        assert "Tesco" in out

    def test_grep_account_invalid_regex(self, session_with_book, capsys):
        session_with_book.cmd_grep(
            ["Tesco", "--account", "[bad", "--account-regex"]
        )
        err = capsys.readouterr().err
        assert "Error" in err

    def test_grep_amount_min(self, session_with_book, capsys):
        session_with_book.cmd_grep(["Tesco", "--amount", "40.."])
        out = capsys.readouterr().out
        assert "Tesco" in out

    def test_grep_amount_max(self, session_with_book, capsys):
        session_with_book.cmd_grep(["Tesco", "--amount", "..50"])
        out = capsys.readouterr().out
        assert "Tesco" in out

    def test_grep_offset(self, session_with_book, capsys):
        session_with_book.output_format = "json"
        session_with_book.cmd_grep(["Tesco", "--offset", "0", "--limit", "1"])
        out = capsys.readouterr().out
        import json

        data = json.loads(out)
        assert len(data) == 1

    def test_grep_full_tx(self, session_with_book, capsys):
        session_with_book.cmd_grep(["Tesco", "--full-tx"])
        out = capsys.readouterr().out
        assert "Tesco" in out

    def test_grep_before_date(self, session_with_book, capsys):
        session_with_book.output_format = "json"
        session_with_book.cmd_grep(["", "--regex", "--before", "2026-01-10"])
        out = capsys.readouterr().out
        import json

        data = json.loads(out)
        for row in data:
            assert row["date"] < "2026-01-10"


# ===================================================================
# Ledger: extended filter coverage
# ===================================================================


class TestLedgerExtended:
    def test_ledger_before_date(self, session_with_book, capsys):
        session_with_book.output_format = "json"
        session_with_book.cmd_ledger(["Checking", "--before", "2026-01-10"])
        out = capsys.readouterr().out
        import json

        data = json.loads(out)
        for row in data:
            assert row["date"] < "2026-01-10"

    def test_ledger_amount_min(self, session_with_book, capsys):
        session_with_book.output_format = "json"
        session_with_book.cmd_ledger(["Checking", "--amount", "100.."])
        out = capsys.readouterr().out
        import json

        data = json.loads(out)
        for row in data:
            assert Decimal(row["amount"]) >= 100

    def test_ledger_amount_max(self, session_with_book, capsys):
        session_with_book.output_format = "json"
        session_with_book.cmd_ledger(["Checking", "--amount", "..50"])
        out = capsys.readouterr().out
        import json

        data = json.loads(out)
        for row in data:
            assert Decimal(row["amount"]) <= 50

    def test_ledger_offset_limit(self, session_with_book, capsys):
        session_with_book.output_format = "json"
        session_with_book.cmd_ledger(
            ["Checking", "--offset", "1", "--limit", "2"]
        )
        out = capsys.readouterr().out
        import json

        data = json.loads(out)
        assert len(data) == 2

    def test_ledger_invalid_regex(self, session_with_book, capsys):
        session_with_book.cmd_ledger(["[bad", "--account-regex"])
        err = capsys.readouterr().err
        assert "Error" in err
