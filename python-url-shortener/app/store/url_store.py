"""URL mapping store backed by SQLite via SQLAlchemy (async).

Provides durable persistence for short-code ↔ original-URL mappings.
All public methods are coroutines and must be awaited.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Column,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    select,
    text,
    update,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from app.exceptions import StorageError, StorageWriteError
from app.models import Mapping

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema definition
# ---------------------------------------------------------------------------

metadata = MetaData()

url_mappings = Table(
    "url_mappings",
    metadata,
    Column("short_code", String, primary_key=True),
    Column("original_url", Text, nullable=False),
    Column("created_at", String, nullable=False),   # ISO 8601 UTC text
    Column("access_count", Integer, nullable=False, default=0),
    Column("expires_at", String, nullable=True),     # ISO 8601 UTC text or NULL
    Index("idx_original_url", "original_url"),
)


# ---------------------------------------------------------------------------
# Helper converters
# ---------------------------------------------------------------------------

def _dt_to_str(dt: datetime | None) -> str | None:
    """Serialise a datetime to an ISO 8601 UTC string for storage."""
    if dt is None:
        return None
    # Normalise to UTC-aware before formatting.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _str_to_dt(value: str | None) -> datetime | None:
    """Deserialise an ISO 8601 UTC string from storage to a timezone-aware datetime."""
    if value is None:
        return None
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _row_to_mapping(row: object) -> Mapping:
    """Convert a SQLAlchemy Row to a :class:`~app.models.Mapping`."""
    return Mapping(
        short_code=row.short_code,
        original_url=row.original_url,
        created_at=_str_to_dt(row.created_at),
        access_count=row.access_count,
        expires_at=_str_to_dt(row.expires_at),
    )


# ---------------------------------------------------------------------------
# URLStore
# ---------------------------------------------------------------------------

class URLStore:
    """Async SQLAlchemy-backed persistence store for URL mappings.

    Usage::

        store = URLStore("sqlite+aiosqlite:///./urls.db")
        await store.initialize()

        mapping = await store.create_mapping(Mapping(...))
        found   = await store.find_by_short_code("abc123")
    """

    def __init__(self, db_url: str) -> None:
        self._db_url: str = db_url
        self._engine: Optional[AsyncEngine] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Connect to the database, verify reachability, and create tables.

        Raises:
            StorageError: if the database cannot be reached or tables
                          cannot be created.
        """
        try:
            self._engine = create_async_engine(self._db_url, echo=False)
            # Verify the engine can actually open a connection.
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            # Create tables (idempotent).
            async with self._engine.begin() as conn:
                await conn.run_sync(metadata.create_all)
        except StorageError:
            raise
        except Exception as exc:
            logger.error("Failed to initialise URLStore: %s", exc)
            raise StorageError(f"Store initialisation failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def find_by_short_code(self, short_code: str) -> Mapping | None:
        """Return the :class:`~app.models.Mapping` for *short_code*, or ``None``.

        Raises:
            StorageError: if the database is unreachable.
        """
        self._require_engine()
        try:
            async with self._engine.connect() as conn:
                stmt = select(url_mappings).where(
                    url_mappings.c.short_code == short_code
                )
                result = await conn.execute(stmt)
                row = result.fetchone()
                return _row_to_mapping(row) if row is not None else None
        except StorageError:
            raise
        except Exception as exc:
            logger.error("find_by_short_code failed for %r: %s", short_code, exc)
            raise StorageError(f"Store read failed: {exc}") from exc

    async def find_by_original_url(self, original_url: str) -> Mapping | None:
        """Return the :class:`~app.models.Mapping` for *original_url*, or ``None``.

        Raises:
            StorageError: if the database is unreachable.
        """
        self._require_engine()
        try:
            async with self._engine.connect() as conn:
                stmt = select(url_mappings).where(
                    url_mappings.c.original_url == original_url
                )
                result = await conn.execute(stmt)
                row = result.fetchone()
                return _row_to_mapping(row) if row is not None else None
        except StorageError:
            raise
        except Exception as exc:
            logger.error(
                "find_by_original_url failed for %r: %s", original_url, exc
            )
            raise StorageError(f"Store read failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    async def create_mapping(self, mapping: Mapping) -> Mapping:
        """Persist *mapping* and return it.

        Raises:
            StorageWriteError: if the write to durable storage fails.
        """
        self._require_engine()
        try:
            async with self._engine.begin() as conn:
                await conn.execute(
                    url_mappings.insert().values(
                        short_code=mapping.short_code,
                        original_url=mapping.original_url,
                        created_at=_dt_to_str(mapping.created_at),
                        access_count=mapping.access_count,
                        expires_at=_dt_to_str(mapping.expires_at),
                    )
                )
            return mapping
        except StorageWriteError:
            raise
        except Exception as exc:
            logger.error(
                "create_mapping failed for short_code=%r: %s",
                mapping.short_code,
                exc,
            )
            raise StorageWriteError(f"Store write failed: {exc}") from exc

    async def increment_access_count(self, short_code: str) -> None:
        """Atomically increment the access count for *short_code*.

        This method is **fire-and-forget**: any failure is logged at WARNING
        level but never re-raised, so the caller's response is never blocked.
        """
        if self._engine is None:
            logger.warning(
                "increment_access_count called before initialize(); "
                "short_code=%r — skipping",
                short_code,
            )
            return
        try:
            async with self._engine.begin() as conn:
                stmt = (
                    update(url_mappings)
                    .where(url_mappings.c.short_code == short_code)
                    .values(access_count=url_mappings.c.access_count + 1)
                )
                await conn.execute(stmt)
        except Exception as exc:
            logger.warning(
                "increment_access_count failed for short_code=%r: %s",
                short_code,
                exc,
            )
            # Intentionally not re-raised — fire-and-forget.

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health_probe(self, timeout: float = 1.0) -> bool:
        """Run a lightweight ``SELECT 1`` against the database.

        Args:
            timeout: Maximum number of seconds to wait for the probe.

        Returns:
            ``True`` if the probe completed successfully within *timeout*,
            ``False`` otherwise.
        """
        if self._engine is None:
            return False
        try:
            async with asyncio.timeout(timeout):
                async with self._engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
            return True
        except Exception as exc:
            logger.warning("health_probe failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_engine(self) -> None:
        """Raise :exc:`~app.exceptions.StorageError` if ``initialize()`` has not been called."""
        if self._engine is None:
            raise StorageError(
                "URLStore has not been initialised; call initialize() first."
            )
