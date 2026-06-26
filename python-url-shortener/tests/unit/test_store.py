"""Unit tests for URLStore — store layer.

Requirements: 2.4, 3.3, 3.5
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.exceptions import StorageError, StorageWriteError
from app.models import Mapping
from app.store.url_store import URLStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mapping(short_code: str = "abc123", original_url: str = "https://example.com") -> Mapping:
    return Mapping(
        short_code=short_code,
        original_url=original_url,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        access_count=0,
        expires_at=None,
    )


# ---------------------------------------------------------------------------
# initialize()
# ---------------------------------------------------------------------------

class TestInitialize:
    """initialize() raises StorageError when the DB is unreachable."""

    @pytest.mark.asyncio
    async def test_raises_storage_error_on_unreachable_db(self):
        """Requirement 2.4 — store init failure surfaces as StorageError."""
        store = URLStore("sqlite+aiosqlite:///nonexistent_dir/db.sqlite")

        # Patch create_async_engine so the connect attempt raises immediately.
        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.execute.side_effect = Exception("connection refused")

        # Use a proper async context manager for engine.connect()
        mock_engine.connect.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine.connect.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.store.url_store.create_async_engine", return_value=mock_engine):
            with pytest.raises(StorageError, match="Store initialisation failed"):
                await store.initialize()

    @pytest.mark.asyncio
    async def test_raises_storage_error_when_select_1_fails(self):
        """StorageError wraps any underlying engine/connection error."""
        store = URLStore("sqlite+aiosqlite:///:memory:")

        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.execute.side_effect = Exception("DB not available")

        mock_engine.connect.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine.connect.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.store.url_store.create_async_engine", return_value=mock_engine):
            with pytest.raises(StorageError):
                await store.initialize()


# ---------------------------------------------------------------------------
# create_mapping()
# ---------------------------------------------------------------------------

class TestCreateMapping:
    """create_mapping() raises StorageWriteError on DB write failure."""

    @pytest.mark.asyncio
    async def test_raises_storage_write_error_on_db_failure(self):
        """Requirement 3.3 — write failures raise StorageWriteError."""
        store = URLStore("sqlite+aiosqlite:///:memory:")

        # Inject a mock engine that raises on begin/execute.
        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.execute.side_effect = Exception("disk full")

        mock_engine.begin.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine.begin.return_value.__aexit__ = AsyncMock(return_value=False)

        store._engine = mock_engine

        with pytest.raises(StorageWriteError, match="Store write failed"):
            await store.create_mapping(_make_mapping())

    @pytest.mark.asyncio
    async def test_storage_write_error_is_not_wrapped_again(self):
        """An already-raised StorageWriteError must propagate unchanged."""
        store = URLStore("sqlite+aiosqlite:///:memory:")

        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.execute.side_effect = StorageWriteError("already a write error")

        mock_engine.begin.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine.begin.return_value.__aexit__ = AsyncMock(return_value=False)

        store._engine = mock_engine

        with pytest.raises(StorageWriteError, match="already a write error"):
            await store.create_mapping(_make_mapping())


# ---------------------------------------------------------------------------
# find_by_short_code()
# ---------------------------------------------------------------------------

class TestFindByShortCode:
    """find_by_short_code() returns None for unknown codes."""

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_code(self):
        """Requirement 3.3 — missing short code returns None, not an error."""
        store = URLStore("sqlite+aiosqlite:///:memory:")

        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None  # simulate no row found
        mock_conn.execute.return_value = mock_result

        mock_engine.connect.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine.connect.return_value.__aexit__ = AsyncMock(return_value=False)

        store._engine = mock_engine

        result = await store.find_by_short_code("does_not_exist")
        assert result is None

    @pytest.mark.asyncio
    async def test_raises_storage_error_if_not_initialized(self):
        """find_by_short_code raises StorageError when engine is None."""
        store = URLStore("sqlite+aiosqlite:///:memory:")
        # _engine is None by default

        with pytest.raises(StorageError, match="not been initialised"):
            await store.find_by_short_code("abc123")


# ---------------------------------------------------------------------------
# find_by_original_url()
# ---------------------------------------------------------------------------

class TestFindByOriginalUrl:
    """find_by_original_url() returns None for unknown URLs."""

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_url(self):
        """Requirement 3.3 — missing original URL returns None."""
        store = URLStore("sqlite+aiosqlite:///:memory:")

        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_conn.execute.return_value = mock_result

        mock_engine.connect.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine.connect.return_value.__aexit__ = AsyncMock(return_value=False)

        store._engine = mock_engine

        result = await store.find_by_original_url("https://unknown.example.com")
        assert result is None

    @pytest.mark.asyncio
    async def test_raises_storage_error_if_not_initialized(self):
        """find_by_original_url raises StorageError when engine is None."""
        store = URLStore("sqlite+aiosqlite:///:memory:")

        with pytest.raises(StorageError, match="not been initialised"):
            await store.find_by_original_url("https://example.com")


# ---------------------------------------------------------------------------
# increment_access_count()
# ---------------------------------------------------------------------------

class TestIncrementAccessCount:
    """increment_access_count() is fire-and-forget: failures are logged, not raised."""

    @pytest.mark.asyncio
    async def test_does_not_raise_on_db_failure(self):
        """Requirement 3.5 — write failure must be swallowed silently."""
        store = URLStore("sqlite+aiosqlite:///:memory:")

        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.execute.side_effect = Exception("update failed")

        mock_engine.begin.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine.begin.return_value.__aexit__ = AsyncMock(return_value=False)

        store._engine = mock_engine

        # Must NOT raise — returns None silently.
        result = await store.increment_access_count("abc123")
        assert result is None

    @pytest.mark.asyncio
    async def test_logs_warning_on_failure(self, caplog):
        """Failure must produce a warning log entry."""
        import logging

        store = URLStore("sqlite+aiosqlite:///:memory:")

        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.execute.side_effect = Exception("update failed")

        mock_engine.begin.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine.begin.return_value.__aexit__ = AsyncMock(return_value=False)

        store._engine = mock_engine

        with caplog.at_level(logging.WARNING, logger="app.store.url_store"):
            await store.increment_access_count("abc123")

        assert any("increment_access_count" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_does_not_raise_when_engine_is_none(self):
        """Calling before initialize() should log a warning but not raise."""
        store = URLStore("sqlite+aiosqlite:///:memory:")
        # _engine is None

        result = await store.increment_access_count("abc123")
        assert result is None


# ---------------------------------------------------------------------------
# health_probe()
# ---------------------------------------------------------------------------

class TestHealthProbe:
    """health_probe() returns False on timeout or failure."""

    @pytest.mark.asyncio
    async def test_returns_false_when_engine_is_none(self):
        """health_probe returns False if initialize() was never called."""
        store = URLStore("sqlite+aiosqlite:///:memory:")
        result = await store.health_probe()
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_timeout(self):
        """Requirement 3.5 — health_probe returns False when SELECT 1 times out."""
        store = URLStore("sqlite+aiosqlite:///:memory:")

        mock_engine = MagicMock()
        mock_conn = AsyncMock()

        # Simulate a hanging SELECT 1 that will be cancelled by asyncio.timeout.
        async def slow_execute(*args, **kwargs):
            await asyncio.sleep(10)  # longer than any timeout used in the test

        mock_conn.execute.side_effect = slow_execute

        mock_engine.connect.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine.connect.return_value.__aexit__ = AsyncMock(return_value=False)

        store._engine = mock_engine

        result = await store.health_probe(timeout=0.05)
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_connection_error(self):
        """health_probe returns False when the connection raises an exception."""
        store = URLStore("sqlite+aiosqlite:///:memory:")

        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.execute.side_effect = Exception("connection error")

        mock_engine.connect.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine.connect.return_value.__aexit__ = AsyncMock(return_value=False)

        store._engine = mock_engine

        result = await store.health_probe()
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_on_success(self):
        """health_probe returns True when SELECT 1 completes successfully."""
        store = URLStore("sqlite+aiosqlite:///:memory:")

        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.execute.return_value = MagicMock()

        mock_engine.connect.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine.connect.return_value.__aexit__ = AsyncMock(return_value=False)

        store._engine = mock_engine

        result = await store.health_probe()
        assert result is True
