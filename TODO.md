# TODO — gcg Code Review Findings

Findings from code review, ordered by priority.

## P1 — Bugs / Correctness

### Fix environment variable name mismatch
SPEC.md and README reference `GCG_BOOK`, but `config.py:89` uses
`GCG_DEFAULT_BOOK_PATH`. Anyone following the docs sets the wrong env var.

Action: Favour GCG_DEFAULT_BOOK_PATH, drop GCG_BOOK.
Status: Pending

### Fix book path resolution order to match spec
Three documents give three different priority orders. The spec says
`--book` > env var > config file > built-in default, but the code does
`--book` > config file > env var (and the built-in default is missing
entirely). Reconcile code, SPEC.md, and README to a single agreed order.

Action: Pick whichever order is most logical, then reconcile code, spec and readme
Status: Pending

### Fix `--full-tx` ignoring `--sort`/`--limit`/`--offset`
In `cmd_grep` (cli.py:625-650), sort/limit/offset are applied to the flat
SplitRow list, but `_splits_to_transactions` is called on the original
`matching_splits`, bypassing those constraints. The resulting `tx_rows`
are never sorted. SPEC §10 says sorting applies to transaction objects
when `--full-tx` is used.

Action: Conform to spec
Status: Pending

### Remove or implement `--fields`
cli.py:126-129 defines a `--fields` argument that no command handler ever
reads. Either wire it up or remove it.

Action: Drop the argument
Status: Pending

## P2 — Design / Architecture

### Extract shared logic from cli.py and repl.py
Nearly all command logic is duplicated between the two files (~950 lines
in repl.py). Duplicated functions include `_account_name`,
`_splits_to_rows`, `_splits_to_transactions`, `_sort_rows`,
`_prune_to_matching_paths`, and the full filtering logic in `cmd_grep`
and `cmd_ledger`. Extract into a shared module so bug fixes and features
only need to be applied once.

Action: Refactor as indicated here to a shared file or module
Status: Pending

### Wire up cache search or remove dead code
`CacheManager.search()` (cache.py:199-258) exists but is never called.
`grep` and `ledger` always go through piecash regardless of cache state.
Either use the cache in the read path or remove the unused method.

Action: Drop the cache
Status: Pending

### Fix SQLite connection leaks
In `book.py`, `check_notes_support`, `get_transaction_notes`, and
`get_transaction_notes_batch` open connections without context managers.
Same issue in `currency.py:_lookup_price`. Use `with` statements or
try/finally to prevent leaks on non-sqlite3 exceptions.

Action: Fix.  Prefer `with` over `try/finalize` unless there's a good argument for the latter.
Status: Pending

## P3 — REPL Parity

### Add `--date` range support to REPL
The CLI supports `--date A..B` via `parse_date_range`, but the REPL's
`cmd_grep` and `cmd_ledger` only accept `--after`/`--before` separately.

Action: Fix.
Status: Pending

### Add error handling for REPL amount parsing
In repl.py:440-446, invalid amount strings raise unhandled
`decimal.InvalidOperation`. The CLI wraps this in a friendly
`ArgumentTypeError` via `parse_amount_range`.

Action: Fix
Status: Pending

## P4 — Tests

### Add REPL tests
~995 lines of code with its own argument parsing, session management, and
command dispatch have zero test coverage.

Action: Fix by adding test coverage
Status: Done

### Add `--full-tx` / balanced-context tests
`_splits_to_transactions` and `_select_balanced_splits` have no test
coverage.

Action: Fix by adding test coverage
Status: Pending

### Add currency conversion tests with price data
`CurrencyConverter.get_price()` and `_lookup_price()` are untested,
including the inverse-rate calculation path.

Action: Fix by adding tests
Status: Done

### Add `CacheManager.search()` tests
The search method has no tests (and is currently unused — see P2 item).

Action: Drop cache, as per P2 item
Status: Done

## P5 — Documentation

### Fix SPEC.md typo: "piekash" → "piecash"
SPEC.md:8 says "piekash".

Action: Fix.
Status: Pending

### Fix SPEC.md example: `gcg grep -i "tesco"`
SPEC.md:366 — `-i` is the global interactive flag, not case-insensitive.
This example would launch the REPL instead of grepping.

Action: Fix, -i should stay "interactive" and gcg should remain case insensitive unless requesting to preserve case
Status: Pending

### Fix README "Run the CLI directly" suggestion
README line 322 suggests `python gcg/cli.py --help`, but relative imports
will fail unless the package is installed. Remove or replace with
`python -m gcg --help`.

Action: Fix, recommend `python -m gcg --help` or (better?) `gcg --help`.
Status: Pending

### Reconcile all docs for env var names and priority order
README, SPEC.md, CLAUDE.md, and config.py must agree on the env var name
and the resolution order for book path.

Action: Fix, possibly already done with P1 bugs.
Status: Pending

### Add a CHANGELOG
The release checklist in PyPi.md references a CHANGELOG that doesn't
exist.

Action: Create a changelog and populate it for this initial commit.
Status: Pending

### Consider single source of truth for version
Version is duplicated in `__init__.py` and `pyproject.toml`. Consider
`setuptools-scm` or dynamic version reading to avoid drift.

Action: Use setuptools-scm.  Document in PyPi.md how to use it (the git command to set the tag and the format to use) as part of the pip publishing process.
Status: Pending

## P6 — Minor / Low Priority

### Replace O(n) GUID lookups with SQL queries
`cmd_tx` iterates all transactions; `cmd_split` iterates all accounts and
splits. Direct `SELECT ... WHERE guid = ?` would be faster for large
books.

Action: Fix.
Status: Pending

### Hold currency converter connection open
`_lookup_price` opens and closes a connection on every call. Holding one
open for the converter's lifetime would reduce overhead.

Action: Fix.
Status: Pending

### Fix `check_notes_support` ineffective `LIMIT 1`
book.py:73 — `SELECT COUNT(*) ... LIMIT 1` is redundant; `COUNT(*)`
always returns one row. Use `SELECT EXISTS(...)` instead.

Action: Fix.
Status: Pending

### Clean up `hasattr`/`getattr` pattern for subparser attributes
cli.py uses `getattr(args, "full_account", False)` and
`hasattr(args, "no_subtree")` inconsistently. Define shared args on the
parent parser or add defaults to each subparser.

Action: Analyse the right solution and fix.  Make sure you document in the git commit why ou've chosen the solution you have.
Status: Pending

### Move `import os` to top of cli.py
cli.py:901 imports `os` inside `cmd_doctor`; the rest of the codebase
uses top-level imports.

Action: Fix.
Status: Pending
