"""Tests for currency conversion."""

import sqlite3
from datetime import date
from decimal import Decimal

import pytest

from gcg.currency import (
    ConversionResult,
    CurrencyConverter,
    determine_display_currency,
    get_account_currencies,
)

# -------------------------------------------------------------------
# Fixture: minimal GnuCash-like SQLite with price data
# -------------------------------------------------------------------


@pytest.fixture
def price_db(tmp_path):
    """Create a minimal SQLite DB with GnuCash commodities + prices."""
    db_path = tmp_path / "prices.gnucash"
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE commodities (
            guid TEXT PRIMARY KEY,
            mnemonic TEXT NOT NULL
        );
        CREATE TABLE prices (
            commodity_guid TEXT NOT NULL,
            currency_guid  TEXT NOT NULL,
            date           TEXT NOT NULL,
            value_num      INTEGER NOT NULL,
            value_denom    INTEGER NOT NULL
        );

        INSERT INTO commodities VALUES ('c_eur', 'EUR');
        INSERT INTO commodities VALUES ('c_gbp', 'GBP');
        INSERT INTO commodities VALUES ('c_usd', 'USD');

        -- GBP -> EUR rate: 1.17 on 2026-01-10
        INSERT INTO prices VALUES (
            'c_gbp', 'c_eur', '2026-01-10', 117, 100
        );
        -- USD -> EUR rate: 0.92 on 2026-01-15
        INSERT INTO prices VALUES (
            'c_usd', 'c_eur', '2026-01-15', 92, 100
        );
        """)
    conn.commit()
    conn.close()
    return db_path


class TestConversionResult:
    """Tests for ConversionResult data class."""

    def test_conversion_result_no_conversion(self):
        """Same currency should not mark as converted."""
        result = ConversionResult(
            amount=Decimal("100"),
            currency="EUR",
            original_amount=Decimal("100"),
            original_currency="EUR",
            fx_rate=Decimal("1"),
            converted=False,
        )
        assert not result.converted
        assert result.fx_rate == Decimal("1")

    def test_conversion_result_with_conversion(self):
        """Different currency should mark as converted."""
        result = ConversionResult(
            amount=Decimal("85"),
            currency="EUR",
            original_amount=Decimal("100"),
            original_currency="GBP",
            fx_rate=Decimal("0.85"),
            converted=True,
        )
        assert result.converted
        assert result.amount == Decimal("85")
        assert result.original_amount == Decimal("100")


class TestDetermineDisplayCurrency:
    """Tests for display currency determination."""

    def test_split_mode_returns_none(self):
        """Split mode should return None (use per-row)."""
        result = determine_display_currency(
            mode="split",
            splits=[],
            account_filter_currencies={"EUR"},
            base_currency="EUR",
        )
        assert result is None

    def test_base_mode_returns_base(self):
        """Base mode should return base currency."""
        result = determine_display_currency(
            mode="base",
            splits=[],
            account_filter_currencies=None,
            base_currency="USD",
        )
        assert result == "USD"

    def test_account_mode_single_currency(self):
        """Account mode with single currency should use it."""
        result = determine_display_currency(
            mode="account",
            splits=[],
            account_filter_currencies={"GBP"},
            base_currency="EUR",
        )
        assert result == "GBP"

    def test_account_mode_multiple_currencies(self):
        """Account mode with multiple currencies should return None."""
        result = determine_display_currency(
            mode="account",
            splits=[],
            account_filter_currencies={"GBP", "USD"},
            base_currency="EUR",
        )
        assert result is None

    def test_auto_mode_account_single_currency(self):
        """Auto mode should use account currency if single."""
        result = determine_display_currency(
            mode="auto",
            splits=[],
            account_filter_currencies={"GBP"},
            base_currency="EUR",
        )
        assert result == "GBP"

    def test_auto_mode_fallback_to_base(self):
        """Auto mode should fall back to base currency."""
        result = determine_display_currency(
            mode="auto",
            splits=[],
            account_filter_currencies={"GBP", "USD", "EUR"},
            base_currency="EUR",
        )
        assert result == "EUR"


class TestGetAccountCurrencies:
    """Tests for getting currencies from accounts."""

    def test_empty_accounts(self):
        """Empty account list should return empty set."""
        result = get_account_currencies([])
        assert result == set()

    def test_accounts_with_commodities(self):
        """Should extract commodities from accounts."""

        class MockCommodity:
            def __init__(self, mnemonic):
                self.mnemonic = mnemonic

        class MockAccount:
            def __init__(self, commodity):
                self.commodity = commodity

        accounts = [
            MockAccount(MockCommodity("EUR")),
            MockAccount(MockCommodity("GBP")),
            MockAccount(MockCommodity("EUR")),  # Duplicate
        ]

        result = get_account_currencies(accounts)
        assert result == {"EUR", "GBP"}

    def test_accounts_without_commodity(self):
        """Accounts without commodity should be skipped."""

        class MockAccount:
            commodity = None

        accounts = [MockAccount(), MockAccount()]
        result = get_account_currencies(accounts)
        assert result == set()


# ===================================================================
# CurrencyConverter — get_price
# ===================================================================


class TestGetPrice:
    def test_same_currency_returns_one(self, price_db):
        conv = CurrencyConverter(price_db)
        rate = conv.get_price("EUR", "EUR", date(2026, 1, 10))
        assert rate == Decimal("1")

    def test_direct_lookup(self, price_db):
        conv = CurrencyConverter(price_db)
        rate = conv.get_price("GBP", "EUR", date(2026, 1, 10))
        assert rate == Decimal("117") / Decimal("100")

    def test_inverse_lookup(self, price_db):
        """EUR->GBP should use the inverse of the stored GBP->EUR rate."""
        conv = CurrencyConverter(price_db)
        rate = conv.get_price("EUR", "GBP", date(2026, 1, 10))
        expected = Decimal("1") / (Decimal("117") / Decimal("100"))
        assert rate == expected

    def test_cache_hit(self, price_db):
        conv = CurrencyConverter(price_db)
        rate1 = conv.get_price("GBP", "EUR", date(2026, 1, 10))
        rate2 = conv.get_price("GBP", "EUR", date(2026, 1, 10))
        assert rate1 == rate2
        # The key should be in the cache after the first call
        assert ("GBP", "EUR", date(2026, 1, 10)) in conv._price_cache

    def test_reverse_cache_hit(self, price_db):
        """After looking up GBP->EUR, EUR->GBP should come from cache."""
        conv = CurrencyConverter(price_db)
        conv.get_price("GBP", "EUR", date(2026, 1, 10))
        # Now the forward key is cached; reverse lookup should use it
        rate = conv.get_price("EUR", "GBP", date(2026, 1, 10))
        assert rate is not None

    def test_no_price_found(self, price_db):
        """Currency pair with no price data returns None."""
        conv = CurrencyConverter(price_db)
        rate = conv.get_price("GBP", "USD", date(2026, 1, 10))
        assert rate is None

    def test_outside_lookback_window(self, price_db):
        """Price older than lookback_days should not be found."""
        conv = CurrencyConverter(price_db, lookback_days=5)
        # Price is on 2026-01-10; querying 2026-02-01 is 22 days later
        rate = conv.get_price("GBP", "EUR", date(2026, 2, 1))
        assert rate is None

    def test_within_lookback_window(self, price_db):
        """Price within lookback_days should be found."""
        conv = CurrencyConverter(price_db, lookback_days=30)
        rate = conv.get_price("GBP", "EUR", date(2026, 1, 20))
        assert rate == Decimal("117") / Decimal("100")

    def test_invalid_db_path(self, tmp_path):
        """Non-existent DB should return None, not raise."""
        conv = CurrencyConverter(tmp_path / "nonexistent.db")
        rate = conv.get_price("GBP", "EUR", date(2026, 1, 10))
        assert rate is None


# ===================================================================
# CurrencyConverter — convert
# ===================================================================


class TestConvert:
    def test_same_currency(self, price_db):
        conv = CurrencyConverter(price_db)
        result = conv.convert(Decimal("100"), "EUR", "EUR", date(2026, 1, 10))
        assert result.converted is False
        assert result.amount == Decimal("100")
        assert result.currency == "EUR"
        assert result.fx_rate == Decimal("1")

    def test_successful_conversion(self, price_db):
        conv = CurrencyConverter(price_db)
        result = conv.convert(Decimal("100"), "GBP", "EUR", date(2026, 1, 10))
        assert result.converted is True
        assert result.currency == "EUR"
        assert result.original_currency == "GBP"
        assert result.original_amount == Decimal("100")
        expected_rate = Decimal("117") / Decimal("100")
        assert result.fx_rate == expected_rate
        assert result.amount == Decimal("100") * expected_rate

    def test_no_rate_available(self, price_db):
        conv = CurrencyConverter(price_db)
        result = conv.convert(Decimal("100"), "GBP", "USD", date(2026, 1, 10))
        assert result.converted is False
        assert result.amount == Decimal("100")
        assert result.currency == "GBP"  # stays original
        assert result.fx_rate is None


# ===================================================================
# determine_display_currency — auto mode with splits
# ===================================================================


class TestAutoModeWithSplits:
    """Cover the auto-mode branch that inspects split currencies."""

    class _Commodity:
        def __init__(self, mnemonic):
            self.mnemonic = mnemonic

    class _Account:
        def __init__(self, commodity):
            self.commodity = commodity

    class _Split:
        def __init__(self, account):
            self.account = account

    def test_auto_single_split_currency(self):
        """Auto mode: all splits share one currency → use it."""
        splits = [
            self._Split(self._Account(self._Commodity("GBP"))),
            self._Split(self._Account(self._Commodity("GBP"))),
        ]
        result = determine_display_currency(
            mode="auto",
            splits=splits,
            account_filter_currencies=None,
            base_currency="EUR",
        )
        assert result == "GBP"

    def test_auto_multiple_split_currencies(self):
        """Auto mode: mixed currencies → fall back to base."""
        splits = [
            self._Split(self._Account(self._Commodity("GBP"))),
            self._Split(self._Account(self._Commodity("USD"))),
        ]
        result = determine_display_currency(
            mode="auto",
            splits=splits,
            account_filter_currencies=None,
            base_currency="EUR",
        )
        assert result == "EUR"

    def test_auto_no_commodity_on_splits(self):
        """Auto mode: splits without commodity → fall back to base."""
        splits = [self._Split(self._Account(None))]
        result = determine_display_currency(
            mode="auto",
            splits=splits,
            account_filter_currencies=None,
            base_currency="EUR",
        )
        assert result == "EUR"
