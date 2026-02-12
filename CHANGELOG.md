# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Interactive REPL `--date A..B` range support for grep and ledger
- REPL error handling for invalid amount strings
- SQLAlchemy-based GUID lookups for `tx` and `split` commands
- Shared module (`gcg/shared.py`) for code reused by CLI and REPL
- `setuptools-scm` for automatic version management from git tags

### Fixed
- Environment variable name: standardised on `GCG_DEFAULT_BOOK_PATH`
- Book path resolution order now matches spec: `--book` > env var > config file > default
- `--full-tx` now respects `--sort`, `--limit`, and `--offset`
- SQLite connection leaks in `book.py` and `currency.py` (now use context managers)
- `check_notes_support` uses `SELECT EXISTS` instead of redundant `COUNT(*) LIMIT 1`
- Currency converter holds DB connection open for its lifetime instead of reconnecting per query
- SPEC.md typo: "piekash" corrected to "piecash"
- SPEC.md example: removed `-i` flag (interactive, not case-insensitive)
- README: removed broken `python gcg/cli.py --help` suggestion

### Removed
- Unused `--fields` CLI argument (was defined but never read)
- Dead `CacheManager.search()` method (was never called)

### Changed
- `import os` moved to top of `cli.py` (was inside `cmd_doctor`)
- Replaced `hasattr`/`getattr` pattern with `set_defaults()` on parent parser
- Extracted duplicated logic from `cli.py` and `repl.py` into `gcg/shared.py`

## [0.1.0] - 2026-02-11

### Added
- Initial release
- `accounts`, `grep`, `ledger`, `tx`, `split`, `doctor`, `cache` commands
- Multi-currency conversion with price database lookups
- Table, CSV, and JSON output formats
- Interactive REPL with readline support
- Optional sidecar SQLite cache with FTS5
- Configuration via TOML file, environment variable, or CLI flags
