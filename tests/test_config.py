"""Tests for configuration loading."""

from pathlib import Path

from gcg.config import (
    Config,
    DEFAULT_BASE_CURRENCY,
    DEFAULT_FX_LOOKBACK_DAYS,
    get_xdg_config_home,
    get_xdg_cache_home,
    get_xdg_state_home,
    load_config,
    load_config_file,
)


class TestXDGPaths:
    """Tests for XDG path resolution."""

    def test_xdg_config_home_default(self, monkeypatch):
        """Default XDG config home should be ~/.config."""
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        result = get_xdg_config_home()
        assert result == Path.home() / ".config"

    def test_xdg_config_home_custom(self, monkeypatch):
        """Custom XDG_CONFIG_HOME should be respected."""
        monkeypatch.setenv("XDG_CONFIG_HOME", "/custom/config")
        result = get_xdg_config_home()
        assert result == Path("/custom/config")

    def test_xdg_cache_home_default(self, monkeypatch):
        """Default XDG cache home should be ~/.cache."""
        monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
        result = get_xdg_cache_home()
        assert result == Path.home() / ".cache"

    def test_xdg_state_home_default(self, monkeypatch):
        """Default XDG state home should be ~/.local/state."""
        monkeypatch.delenv("XDG_STATE_HOME", raising=False)
        result = get_xdg_state_home()
        assert result == Path.home() / ".local" / "state"


class TestConfigDefaults:
    """Tests for configuration defaults."""

    def test_config_default_values(self):
        """Config should have correct default values."""
        config = Config()
        assert config.base_currency == DEFAULT_BASE_CURRENCY
        assert config.fx_lookback_days == DEFAULT_FX_LOOKBACK_DAYS
        assert config.output_format == "table"
        assert config.show_header is True
        assert config.currency_mode == "auto"
        assert config.cache_enabled is True

    def test_config_derived_paths(self):
        """Config should set derived paths in __post_init__."""
        config = Config()
        assert config.cache_path is not None
        assert config.history_path is not None
        assert "gcg" in str(config.cache_path)
        assert "gcg" in str(config.history_path)


class TestConfigResolution:
    """Tests for book path resolution."""

    def test_resolve_book_path_from_config(self, monkeypatch):
        """Book path set in config should be used."""
        monkeypatch.delenv("GCG_DEFAULT_BOOK_PATH", raising=False)
        config = Config(book_path=Path("/custom/book.gnucash"))
        result = config.resolve_book_path()
        assert result == Path("/custom/book.gnucash")

    def test_resolve_book_path_from_default_env(self, monkeypatch):
        """GCG_DEFAULT_BOOK_PATH should be used as fallback default."""
        monkeypatch.setenv("GCG_DEFAULT_BOOK_PATH", "/default/book.gnucash")
        config = Config()
        result = config.resolve_book_path()
        assert result == Path("/default/book.gnucash")

    def test_resolve_book_path_config_overrides_default_env(self, monkeypatch):
        """Config book_path should override GCG_DEFAULT_BOOK_PATH."""
        monkeypatch.setenv("GCG_DEFAULT_BOOK_PATH", "/default/book.gnucash")
        config = Config(book_path=Path("/config/book.gnucash"))
        result = config.resolve_book_path()
        assert result == Path("/config/book.gnucash")

    def test_resolve_book_path_none_when_not_configured(self, monkeypatch):
        """None should be returned when no book path is configured."""
        monkeypatch.delenv("GCG_DEFAULT_BOOK_PATH", raising=False)
        config = Config()
        result = config.resolve_book_path()
        assert result is None


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_cli_overrides(self):
        """CLI arguments should override defaults."""
        config = load_config(
            book_path="/cli/book.gnucash",
            base_currency="USD",
            fx_lookback_days=60,
            output_format="json",
        )
        assert config.book_path == Path("/cli/book.gnucash")
        assert config.base_currency == "USD"
        assert config.fx_lookback_days == 60
        assert config.output_format == "json"

    def test_load_config_partial_overrides(self):
        """Partial CLI args should leave other defaults."""
        config = load_config(output_format="csv")
        assert config.output_format == "csv"
        assert config.base_currency == DEFAULT_BASE_CURRENCY
        assert config.fx_lookback_days == DEFAULT_FX_LOOKBACK_DAYS

    def test_load_config_show_header_override(self):
        config = load_config(show_header=False)
        assert config.show_header is False

    def test_load_config_currency_mode_override(self):
        config = load_config(currency_mode="base")
        assert config.currency_mode == "base"


class TestLoadConfigFile:
    """Tests for loading config from TOML file."""

    def test_no_config_file(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        result = load_config_file()
        assert result == {}

    def test_valid_config_file(self, monkeypatch, tmp_path):
        config_dir = tmp_path / "gcg"
        config_dir.mkdir()
        config_file = config_dir / "config.toml"
        config_file.write_text(
            'book = "/path/to/book.gnucash"\n'
            "\n"
            "[currency]\n"
            'base = "USD"\n'
            "fx_lookback_days = 60\n"
            'mode = "base"\n'
            "\n"
            "[output]\n"
            'format = "json"\n'
            "header = false\n"
            "\n"
            "[cache]\n"
            "enabled = false\n"
            'path = "/tmp/cache.sqlite"\n'
        )
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        result = load_config_file()
        assert result["book"] == "/path/to/book.gnucash"
        assert result["currency"]["base"] == "USD"
        assert result["currency"]["fx_lookback_days"] == 60
        assert result["currency"]["mode"] == "base"
        assert result["output"]["format"] == "json"
        assert result["output"]["header"] is False
        assert result["cache"]["enabled"] is False
        assert result["cache"]["path"] == "/tmp/cache.sqlite"

    def test_invalid_toml_file(self, monkeypatch, tmp_path, capsys):
        config_dir = tmp_path / "gcg"
        config_dir.mkdir()
        config_file = config_dir / "config.toml"
        config_file.write_text("this is [not valid toml")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        result = load_config_file()
        assert result == {}
        err = capsys.readouterr().err
        assert "Warning" in err


class TestLoadConfigFromFile:
    """Test that load_config picks up values from a TOML file."""

    def test_full_config_from_file(self, monkeypatch, tmp_path):
        config_dir = tmp_path / "gcg"
        config_dir.mkdir()
        config_file = config_dir / "config.toml"
        config_file.write_text(
            'book = "/file/book.gnucash"\n'
            "\n"
            "[currency]\n"
            'base = "GBP"\n'
            "fx_lookback_days = 90\n"
            'mode = "split"\n'
            "\n"
            "[output]\n"
            'format = "csv"\n'
            "header = false\n"
            "\n"
            "[cache]\n"
            "enabled = false\n"
            'path = "/tmp/my_cache.sqlite"\n'
        )
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        config = load_config()
        assert config.book_path == Path("/file/book.gnucash")
        assert config.base_currency == "GBP"
        assert config.fx_lookback_days == 90
        assert config.currency_mode == "split"
        assert config.output_format == "csv"
        assert config.show_header is False
        assert config.cache_enabled is False
        assert config.cache_path == Path("/tmp/my_cache.sqlite")

    def test_cli_overrides_file(self, monkeypatch, tmp_path):
        config_dir = tmp_path / "gcg"
        config_dir.mkdir()
        config_file = config_dir / "config.toml"
        config_file.write_text(
            'book = "/file/book.gnucash"\n' '[currency]\nbase = "GBP"\n'
        )
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        config = load_config(
            book_path="/cli/book.gnucash",
            base_currency="JPY",
        )
        assert config.book_path == Path("/cli/book.gnucash")
        assert config.base_currency == "JPY"
