"""
gcg: Grep-like search and reporting for GnuCash SQLite books.

A read-only command-line tool that opens a GnuCash book stored in SQLite
and provides grep/ledger-style search and reporting.
"""

try:
    from gcg._version import version as __version__
except ImportError:
    __version__ = "0.0.0.dev0"
