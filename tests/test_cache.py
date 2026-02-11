"""Tests for the cache module."""

import sqlite3

import pytest

from gcg.cache import CacheManager

# -------------------------------------------------------------------
# Fixture: CacheManager with a real GnuCash book
# -------------------------------------------------------------------


@pytest.fixture
def cache_mgr(tmp_path, test_book_path):
    """CacheManager pointing at a temp cache path and the test book."""
    cache_path = tmp_path / "cache" / "cache.sqlite"
    return CacheManager(cache_path, test_book_path)


@pytest.fixture
def built_cache(cache_mgr, test_book_path):
    """A CacheManager with a fully built cache."""
    import warnings

    warnings.filterwarnings("ignore")

    from gcg.book import open_gnucash_book

    with open_gnucash_book(test_book_path) as (book, info):
        cache_mgr.build(book, info)
    return cache_mgr


# ===================================================================
# status()
# ===================================================================


class TestStatus:
    def test_status_no_cache(self, cache_mgr):
        status = cache_mgr.status()
        assert status["exists"] is False
        assert "path" in status

    def test_status_with_cache(self, built_cache):
        status = built_cache.status()
        assert status["exists"] is True
        assert status["size_bytes"] > 0
        assert "modified" in status
        assert status["split_count"] > 0
        assert status["schema_version"] == CacheManager.SCHEMA_VERSION
        assert status["source_book"] is not None
        assert status["build_time"] is not None

    def test_status_corrupt_cache(self, tmp_path, test_book_path):
        """A non-SQLite file at the cache path should not crash."""
        cache_path = tmp_path / "bad.sqlite"
        cache_path.write_text("not a database")
        mgr = CacheManager(cache_path, test_book_path)
        status = mgr.status()
        assert status["exists"] is True
        assert "error" in status


# ===================================================================
# build()
# ===================================================================


class TestBuild:
    def test_build_creates_cache(self, cache_mgr, test_book_path):
        import warnings

        warnings.filterwarnings("ignore")

        from gcg.book import open_gnucash_book

        assert not cache_mgr.cache_path.exists()
        with open_gnucash_book(test_book_path) as (book, info):
            cache_mgr.build(book, info)
        assert cache_mgr.cache_path.exists()

    def test_build_populates_splits(self, built_cache):
        conn = sqlite3.connect(str(built_cache.cache_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM splits")
        count = cursor.fetchone()[0]
        conn.close()
        assert count > 0

    def test_build_refuses_without_force(self, built_cache, test_book_path):
        import warnings

        warnings.filterwarnings("ignore")

        from gcg.book import open_gnucash_book

        with open_gnucash_book(test_book_path) as (book, info):
            with pytest.raises(ValueError, match="already exists"):
                built_cache.build(book, info, force=False)

    def test_build_force_rebuilds(self, built_cache, test_book_path):
        import warnings

        warnings.filterwarnings("ignore")

        from gcg.book import open_gnucash_book

        with open_gnucash_book(test_book_path) as (book, info):
            built_cache.build(book, info, force=True)
        assert built_cache.cache_path.exists()

    def test_build_creates_parent_directories(self, tmp_path, test_book_path):
        import warnings

        warnings.filterwarnings("ignore")

        from gcg.book import open_gnucash_book

        deep_path = tmp_path / "a" / "b" / "c" / "cache.sqlite"
        mgr = CacheManager(deep_path, test_book_path)
        with open_gnucash_book(test_book_path) as (book, info):
            mgr.build(book, info)
        assert deep_path.exists()


# ===================================================================
# drop()
# ===================================================================


class TestDrop:
    def test_drop_existing(self, built_cache):
        assert built_cache.cache_path.exists()
        result = built_cache.drop()
        assert result is True
        assert not built_cache.cache_path.exists()

    def test_drop_nonexistent(self, cache_mgr):
        result = cache_mgr.drop()
        assert result is False


# ===================================================================
# search()
# ===================================================================


class TestSearch:
    def test_search_fts(self, built_cache):
        results = built_cache.search("Tesco")
        assert len(results) > 0
        assert any("Tesco" in r["description"] for r in results)

    def test_search_fts_no_match(self, built_cache):
        results = built_cache.search("ZZZNOMATCH")
        assert len(results) == 0

    def test_search_like_fallback(self, built_cache):
        results = built_cache.search("tesco", use_fts=False)
        assert len(results) > 0

    def test_search_like_no_match(self, built_cache):
        results = built_cache.search("ZZZNOMATCH", use_fts=False)
        assert len(results) == 0

    def test_search_with_limit(self, built_cache):
        results = built_cache.search("", use_fts=False, limit=1)
        assert len(results) == 1

    def test_search_fts_with_limit(self, built_cache):
        # Search for something broad that matches multiple rows
        results = built_cache.search("Tesco OR salary", limit=1)
        assert len(results) <= 1

    def test_search_no_cache_raises(self, cache_mgr):
        with pytest.raises(ValueError, match="does not exist"):
            cache_mgr.search("anything")
