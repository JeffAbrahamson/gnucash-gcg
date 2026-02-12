# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**gcg** (GnuCash Grep) is a read-only, grep-like CLI tool for searching and reporting from GnuCash SQLite books. It supports multi-currency conversion, multiple output formats (table/CSV/JSON), and an interactive REPL. It never modifies the GnuCash book.

## Build & Development Commands

**Note:** This environment uses `python3` (not `python`).

```bash
# Install in editable mode with dev dependencies
python3 -m pip install -e ".[dev]"

# Run all tests
python3 -m pytest

# Run a specific test file
python3 -m pytest tests/test_cli.py

# Run a single test by name
python3 -m pytest tests/test_cli.py -k "test_name"

# Run with coverage
python3 -m pytest --cov=gcg --cov-report=term-missing

# Check formatting (must pass CI)
python3 -m black --check --verbose --line-length 79 .
python3 -m flake8 .

# Auto-format
python3 -m black --line-length 79 gcg/ tests/

# Run the tool directly during development
python3 -m gcg --help
```

## Code Style

- **Black** formatter with line length **79** characters
- **Flake8** linter: ignores E203 and W503; F401 allowed in `__init__.py`
- Target Python versions: 3.9, 3.10, 3.11, 3.12
- CI runs both `black --check` and `flake8` on every PR

## Architecture

The `gcg/` package has a clear layered structure:

- **cli.py** — Entry point (`main()`), argument parsing via `create_parser()`, command dispatch. All subcommands (accounts, grep, ledger, tx, split, doctor, cache) are handled here.
- **book.py** — GnuCash book access layer. Opens SQLite in read-only mode via piecash. Provides `open_gnucash_book()` context manager, notes detection (`check_notes_support()`), and direct SQL queries.
- **config.py** — `Config` dataclass and `load_config()`. Resolution order: `--book` CLI arg > `GCG_DEFAULT_BOOK_PATH` env var > `~/.config/gcg/config.toml` > hardcoded default.
- **output.py** — Dataclasses (`SplitRow`, `TransactionRow`, `AccountRow`) and `OutputFormatter` for table/CSV/JSON rendering. Uses `tabulate` for tables.
- **currency.py** — `CurrencyConverter` class. Handles display modes (auto/base/split/account), price lookups from GnuCash price DB, rate caching with configurable lookback window.
- **cache.py** — `CacheManager` for an optional sidecar SQLite cache. Denormalizes split+tx+account data with FTS5 for fast text search. Stored at `~/.cache/gcg/cache.sqlite`.
- **repl.py** — `ReplSession` for interactive mode. Readline/prompt_toolkit support, persistent history at `~/.local/state/gcg/history`.

## Key Design Decisions

- All amounts use `Decimal` internally for precision
- The tool opens SQLite in read-only mode (`?mode=ro`) and never falls back to read-write
- Split rows are the default output unit; `--full-tx` expands to transaction blocks
- Date filters: `--after` is inclusive, `--before` is exclusive, `--date A..B` is inclusive on both ends (internally converts to `--before (B + 1 day)`)
- Amount filtering defaults to absolute values; `--signed` enables signed mode
- Custom exceptions: `BookOpenError`, `InvalidPatternError` (in book.py)

## Test Structure

Tests live in `tests/` using pytest. `conftest.py` provides fixtures that create small in-memory GnuCash books for testing. Test files map to modules: `test_cli.py`, `test_config.py`, `test_currency.py`, `test_output.py`, `test_integration.py`. SAWarning from SQLAlchemy is filtered in pytest config.

## Specification

`SPEC.md` contains the detailed functional specification including matching semantics, currency conversion rules, context balancing algorithm for `--full-tx`, and REPL behavior. Consult it for requirements questions.

## Exit Codes

- `0` — matches found or command succeeded
- `1` — no matches / GUID not found
- `2` — error (bad args, regex error, DB open failure)
