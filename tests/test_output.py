"""Tests for output formatting."""

import io
import json
from datetime import date
from decimal import Decimal

import pytest

from gcg.output import (
    AccountRow,
    OutputFormatter,
    SplitRow,
    TransactionRow,
    _truncate,
    _format_amount,
)


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_truncate_short_string(self):
        """Short strings should not be truncated."""
        result = _truncate("hello", 10)
        assert result == "hello"

    def test_truncate_exact_length(self):
        """Strings at exact length should not be truncated."""
        result = _truncate("hello", 5)
        assert result == "hello"

    def test_truncate_long_string(self):
        """Long strings should be truncated with ellipsis."""
        result = _truncate("hello world", 8)
        assert result == "hello..."
        assert len(result) == 8

    def test_format_amount_positive(self):
        """Positive amounts should format correctly."""
        result = _format_amount(Decimal("1234.56"))
        assert result == "1,234.56"

    def test_format_amount_negative(self):
        """Negative amounts should format correctly."""
        result = _format_amount(Decimal("-1234.56"))
        assert result == "-1,234.56"

    def test_format_amount_none(self):
        """None should return empty string."""
        result = _format_amount(None)
        assert result == ""


class TestSplitRow:
    """Tests for SplitRow data class."""

    def test_split_row_to_dict(self):
        """SplitRow should convert to dict correctly."""
        row = SplitRow(
            date=date(2026, 1, 15),
            description="Test transaction",
            account="Assets:Bank",
            memo="Test memo",
            notes="Test notes",
            amount=Decimal("100.00"),
            currency="EUR",
            fx_rate=None,
            tx_guid="tx-123",
            split_guid="split-456",
        )
        result = row.to_dict()

        assert result["date"] == "2026-01-15"
        assert result["description"] == "Test transaction"
        assert result["account"] == "Assets:Bank"
        assert result["memo"] == "Test memo"
        assert result["notes"] == "Test notes"
        assert result["amount"] == "100.00"
        assert result["currency"] == "EUR"
        assert result["fx_rate"] is None
        assert result["tx_guid"] == "tx-123"
        assert result["split_guid"] == "split-456"

    def test_split_row_to_dict_with_conversion(self):
        """SplitRow with conversion should include fx_rate."""
        row = SplitRow(
            date=date(2026, 1, 15),
            description="Test",
            account="Assets:Bank",
            memo=None,
            notes=None,
            amount=Decimal("85.00"),
            currency="EUR",
            fx_rate=Decimal("0.85"),
            tx_guid="tx-123",
            split_guid="split-456",
            amount_orig=Decimal("100.00"),
            currency_orig="GBP",
        )
        result = row.to_dict()

        assert result["amount"] == "85.00"
        assert result["currency"] == "EUR"
        assert result["fx_rate"] == "0.85"
        assert result["amount_orig"] == "100.00"
        assert result["currency_orig"] == "GBP"


class TestAccountRow:
    """Tests for AccountRow data class."""

    def test_account_row_to_dict(self):
        """AccountRow should convert to dict correctly."""
        row = AccountRow(
            name="Assets:Bank:UK",
            type="BANK",
            currency="GBP",
            guid="acc-123",
        )
        result = row.to_dict(show_guid=True)

        assert result["name"] == "Assets:Bank:UK"
        assert result["type"] == "BANK"
        assert result["currency"] == "GBP"
        assert result["guid"] == "acc-123"

    def test_account_row_to_dict_no_guid(self):
        """AccountRow without show_guid should omit guid."""
        row = AccountRow(
            name="Assets:Bank",
            type="BANK",
            currency="EUR",
            guid="acc-123",
        )
        result = row.to_dict(show_guid=False)

        assert "guid" not in result


class TestOutputFormatter:
    """Tests for OutputFormatter class."""

    @pytest.fixture
    def sample_splits(self):
        """Create sample split rows for testing."""
        return [
            SplitRow(
                date=date(2026, 1, 15),
                description="Amazon Purchase",
                account="Expenses:Shopping",
                memo="Order #123",
                notes=None,
                amount=Decimal("50.00"),
                currency="EUR",
                fx_rate=None,
                tx_guid="tx-1",
                split_guid="split-1",
            ),
            SplitRow(
                date=date(2026, 1, 16),
                description="Grocery Store",
                account="Expenses:Food",
                memo=None,
                notes=None,
                amount=Decimal("25.50"),
                currency="EUR",
                fx_rate=None,
                tx_guid="tx-2",
                split_guid="split-2",
            ),
        ]

    def test_format_splits_json(self, sample_splits):
        """JSON output should be valid JSON array."""
        formatter = OutputFormatter(format_type="json")
        output = io.StringIO()
        formatter.format_splits(sample_splits, file=output)

        result = json.loads(output.getvalue())
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["description"] == "Amazon Purchase"
        assert result[1]["amount"] == "25.50"

    def test_format_splits_csv(self, sample_splits):
        """CSV output should have header and rows."""
        formatter = OutputFormatter(format_type="csv")
        output = io.StringIO()
        formatter.format_splits(sample_splits, file=output)

        lines = output.getvalue().strip().split("\n")
        assert len(lines) == 3  # Header + 2 data rows
        assert "date" in lines[0]
        assert "description" in lines[0]

    def test_format_splits_csv_no_header(self, sample_splits):
        """CSV without header should only have data rows."""
        formatter = OutputFormatter(format_type="csv", show_header=False)
        output = io.StringIO()
        formatter.format_splits(sample_splits, file=output)

        lines = output.getvalue().strip().split("\n")
        assert len(lines) == 2  # No header, just data

    def test_format_empty_splits(self):
        """Empty split list should produce no output."""
        formatter = OutputFormatter(format_type="json")
        output = io.StringIO()
        formatter.format_splits([], file=output)
        assert output.getvalue() == ""

    @pytest.fixture
    def sample_accounts(self):
        """Create sample account rows for testing."""
        return [
            AccountRow(name="Assets:Bank", type="BANK", currency="EUR"),
            AccountRow(name="Assets:Cash", type="CASH", currency="EUR"),
        ]

    def test_format_accounts_json(self, sample_accounts):
        """Account JSON output should be valid."""
        formatter = OutputFormatter(format_type="json")
        output = io.StringIO()
        formatter.format_accounts(sample_accounts, file=output)

        result = json.loads(output.getvalue())
        assert len(result) == 2
        assert result[0]["name"] == "Assets:Bank"

    def test_format_accounts_csv(self, sample_accounts):
        """CSV account output should have header and rows."""
        formatter = OutputFormatter(format_type="csv")
        output = io.StringIO()
        formatter.format_accounts(sample_accounts, file=output)
        lines = output.getvalue().strip().split("\n")
        assert len(lines) == 3
        assert "name" in lines[0]

    def test_format_accounts_csv_with_guids(self):
        """CSV accounts with GUIDs should include guid column."""
        rows = [
            AccountRow(name="A", type="BANK", currency="EUR", guid="g1"),
        ]
        formatter = OutputFormatter(format_type="csv", show_guids=True)
        output = io.StringIO()
        formatter.format_accounts(rows, file=output)
        lines = output.getvalue().strip().split("\n")
        assert "guid" in lines[0]
        assert "g1" in lines[1]

    def test_format_accounts_table_no_header(self, sample_accounts):
        """Table accounts without header."""
        formatter = OutputFormatter(format_type="table", show_header=False)
        output = io.StringIO()
        formatter.format_accounts(sample_accounts, file=output)
        text = output.getvalue()
        assert "Account" not in text  # No header
        assert "Assets:Bank" in text

    def test_format_empty_accounts(self):
        """Empty account list should produce no output."""
        formatter = OutputFormatter(format_type="json")
        output = io.StringIO()
        formatter.format_accounts([], file=output)
        assert output.getvalue() == ""

    def test_format_splits_table_with_notes(self):
        """Table splits with notes should show notes column."""
        rows = [
            SplitRow(
                date=date(2026, 1, 1),
                description="Test",
                account="Acc",
                memo=None,
                notes="Some note",
                amount=Decimal("10"),
                currency="EUR",
                fx_rate=None,
                tx_guid="t1",
                split_guid="s1",
            ),
        ]
        formatter = OutputFormatter(format_type="table", include_notes=True)
        output = io.StringIO()
        formatter.format_splits(rows, file=output)
        assert "Notes" in output.getvalue()
        assert "Some note" in output.getvalue()

    def test_format_splits_table_with_orig(self):
        """Table splits with original amounts should show columns."""
        rows = [
            SplitRow(
                date=date(2026, 1, 1),
                description="Test",
                account="Acc",
                memo=None,
                notes=None,
                amount=Decimal("85"),
                currency="EUR",
                fx_rate=Decimal("0.85"),
                tx_guid="t1",
                split_guid="s1",
                amount_orig=Decimal("100"),
                currency_orig="GBP",
            ),
        ]
        formatter = OutputFormatter(format_type="table")
        output = io.StringIO()
        formatter.format_splits(rows, file=output)
        text = output.getvalue()
        assert "Orig Amt" in text
        assert "Orig Ccy" in text
        assert "GBP" in text

    def test_format_splits_table_no_header(self, sample_splits):
        """Table splits without header."""
        formatter = OutputFormatter(format_type="table", show_header=False)
        output = io.StringIO()
        formatter.format_splits(sample_splits, file=output)
        text = output.getvalue()
        assert "Date" not in text
        assert "Amazon" in text

    def test_format_splits_csv_with_notes(self):
        """CSV splits with notes should include notes column."""
        rows = [
            SplitRow(
                date=date(2026, 1, 1),
                description="Test",
                account="Acc",
                memo=None,
                notes="A note",
                amount=Decimal("10"),
                currency="EUR",
                fx_rate=None,
                tx_guid="t1",
                split_guid="s1",
            ),
        ]
        formatter = OutputFormatter(format_type="csv", include_notes=True)
        output = io.StringIO()
        formatter.format_splits(rows, file=output)
        text = output.getvalue()
        assert "notes" in text
        assert "A note" in text

    def test_format_splits_csv_with_orig(self):
        """CSV splits with original amounts."""
        rows = [
            SplitRow(
                date=date(2026, 1, 1),
                description="Test",
                account="Acc",
                memo=None,
                notes=None,
                amount=Decimal("85"),
                currency="EUR",
                fx_rate=Decimal("0.85"),
                tx_guid="t1",
                split_guid="s1",
                amount_orig=Decimal("100"),
                currency_orig="GBP",
            ),
        ]
        formatter = OutputFormatter(format_type="csv")
        output = io.StringIO()
        formatter.format_splits(rows, file=output)
        text = output.getvalue()
        assert "amount_orig" in text
        assert "currency_orig" in text

    def test_format_splits_csv_empty(self):
        """CSV with empty rows should produce no output."""
        formatter = OutputFormatter(format_type="csv")
        output = io.StringIO()
        formatter._format_splits_csv([], file=output)
        assert output.getvalue() == ""


# ===================================================================
# TransactionRow tests
# ===================================================================


class TestTransactionRow:
    """Tests for TransactionRow data class."""

    @pytest.fixture
    def sample_tx(self):
        splits = [
            SplitRow(
                date=date(2026, 1, 15),
                description="Test tx",
                account="Expenses:Food",
                memo="lunch",
                notes=None,
                amount=Decimal("25"),
                currency="EUR",
                fx_rate=None,
                tx_guid="tx-1",
                split_guid="s-1",
            ),
            SplitRow(
                date=date(2026, 1, 15),
                description="Test tx",
                account="Assets:Bank",
                memo=None,
                notes=None,
                amount=Decimal("25"),
                currency="EUR",
                fx_rate=None,
                tx_guid="tx-1",
                split_guid="s-2",
            ),
        ]
        return TransactionRow(
            tx_guid="tx-1",
            date=date(2026, 1, 15),
            description="Test tx",
            notes="A note",
            splits=splits,
        )

    def test_to_dict(self, sample_tx):
        d = sample_tx.to_dict()
        assert d["tx_guid"] == "tx-1"
        assert d["date"] == "2026-01-15"
        assert d["description"] == "Test tx"
        assert d["notes"] == "A note"
        assert len(d["splits"]) == 2

    def test_to_dict_no_notes(self):
        tx = TransactionRow(
            tx_guid="tx-2",
            date=date(2026, 1, 1),
            description="No notes",
            notes=None,
            splits=[],
        )
        d = tx.to_dict()
        assert "notes" not in d


# ===================================================================
# Transaction formatting tests
# ===================================================================


class TestFormatTransactions:
    @pytest.fixture
    def sample_txs(self):
        splits = [
            SplitRow(
                date=date(2026, 1, 15),
                description="Test tx",
                account="Expenses:Food",
                memo="lunch",
                notes=None,
                amount=Decimal("25"),
                currency="EUR",
                fx_rate=None,
                tx_guid="tx-1",
                split_guid="s-1",
            ),
            SplitRow(
                date=date(2026, 1, 15),
                description="Test tx",
                account="Assets:Bank",
                memo=None,
                notes=None,
                amount=Decimal("25"),
                currency="EUR",
                fx_rate=None,
                tx_guid="tx-1",
                split_guid="s-2",
            ),
        ]
        return [
            TransactionRow(
                tx_guid="tx-1",
                date=date(2026, 1, 15),
                description="Test tx",
                notes="A note",
                splits=splits,
            )
        ]

    def test_format_transactions_table(self, sample_txs):
        formatter = OutputFormatter(format_type="table")
        output = io.StringIO()
        formatter.format_transactions(sample_txs, file=output)
        text = output.getvalue()
        assert "Test tx" in text
        assert "Notes: A note" in text
        assert "GUID: tx-1" in text
        assert "Expenses:Food" in text
        assert "Memo: lunch" in text

    def test_format_transactions_json(self, sample_txs):
        formatter = OutputFormatter(format_type="json")
        output = io.StringIO()
        formatter.format_transactions(sample_txs, file=output)
        data = json.loads(output.getvalue())
        assert len(data) == 1
        assert data[0]["tx_guid"] == "tx-1"
        assert len(data[0]["splits"]) == 2

    def test_format_transactions_csv(self, sample_txs):
        formatter = OutputFormatter(format_type="csv")
        output = io.StringIO()
        formatter.format_transactions(sample_txs, file=output)
        lines = output.getvalue().strip().split("\n")
        assert len(lines) == 3  # header + 2 splits

    def test_format_transactions_empty(self):
        formatter = OutputFormatter(format_type="json")
        output = io.StringIO()
        formatter.format_transactions([], file=output)
        assert output.getvalue() == ""

    def test_format_transactions_table_multiple(self):
        """Multiple transactions should have blank line separators."""
        split1 = SplitRow(
            date=date(2026, 1, 1),
            description="Tx1",
            account="Acc",
            memo=None,
            notes=None,
            amount=Decimal("10"),
            currency="EUR",
            fx_rate=None,
            tx_guid="t1",
            split_guid="s1",
        )
        split2 = SplitRow(
            date=date(2026, 1, 2),
            description="Tx2",
            account="Acc",
            memo=None,
            notes=None,
            amount=Decimal("20"),
            currency="EUR",
            fx_rate=None,
            tx_guid="t2",
            split_guid="s2",
        )
        txs = [
            TransactionRow(
                tx_guid="t1",
                date=date(2026, 1, 1),
                description="Tx1",
                notes=None,
                splits=[split1],
            ),
            TransactionRow(
                tx_guid="t2",
                date=date(2026, 1, 2),
                description="Tx2",
                notes=None,
                splits=[split2],
            ),
        ]
        formatter = OutputFormatter(format_type="table")
        output = io.StringIO()
        formatter.format_transactions(txs, file=output)
        text = output.getvalue()
        assert "Tx1" in text
        assert "Tx2" in text


# ===================================================================
# SplitRow with account_guid
# ===================================================================


class TestSplitRowAccountGuid:
    def test_to_dict_with_account_guid(self):
        row = SplitRow(
            date=date(2026, 1, 1),
            description="Test",
            account="Acc",
            memo=None,
            notes=None,
            amount=Decimal("10"),
            currency="EUR",
            fx_rate=None,
            tx_guid="t1",
            split_guid="s1",
            account_guid="ag-1",
        )
        d = row.to_dict()
        assert d["account_guid"] == "ag-1"
