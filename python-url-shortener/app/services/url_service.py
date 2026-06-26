"""URL shortening service — core business logic.

This module contains :class:`URLService`, which orchestrates the interaction
between the HTTP layer, the code generator, and the persistence store.
It is stateless beyond its constructor-injected dependencies and is designed
to be used as a FastAPI dependency via ``app/dependencies.py``.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.exceptions import CodeGenerationError, ConflictError, ExpiredError, NotFoundError
from app.models import Mapping
from app.services.code_generator import CodeGenerator
from app.store.url_store import URLStore

logger = logging.getLogger(__name__)

_MAX_GENERATION_ATTEMPTS = 10


class URLService:
    """Business logic for URL shortening, redirection, and statistics."""

    def __init__(
        self,
        store: URLStore,
        code_generator: CodeGenerator,
        base_url: str,
    ) -> None:
        self._store = store
        self._code_generator = code_generator
        self._base_url = base_url.rstrip("/")

    async def shorten(
        self,
        original_url: str,
        custom_code=None,
        expires_in=None,
    ):
        if custom_code is None:
            existing = await self._store.find_by_original_url(original_url)
            if existing is not None:
                return existing

        expires_at = None
        if expires_in is not None:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        if custom_code is not None:
            conflict = await self._store.find_by_short_code(custom_code)
            if conflict is not None:
                raise ConflictError(f"Short code '{custom_code}' is already in use.")
            short_code = custom_code
        else:
            short_code = await self._generate_unique_code()

        mapping = Mapping(
            short_code=short_code,
            original_url=original_url,
            created_at=datetime.now(timezone.utc),
            access_count=0,
            expires_at=expires_at,
        )
        return await self._store.create_mapping(mapping)

    async def redirect(self, short_code: str):
        mapping = await self._store.find_by_short_code(short_code)
        if mapping is None:
            raise NotFoundError(f"Short code '{short_code}' not found.")

        if mapping.is_expired():
            raise ExpiredError(f"Short code '{short_code}' has expired.")

        asyncio.ensure_future(self._safe_increment(short_code))

        return mapping

    async def get_stats(self, short_code: str):
        mapping = await self._store.find_by_short_code(short_code)
        if mapping is None:
            raise NotFoundError(f"Short code '{short_code}' not found.")
        return mapping

    async def _generate_unique_code(self) -> str:
        for attempt in range(_MAX_GENERATION_ATTEMPTS):
            candidate = self._code_generator.generate()
            existing = await self._store.find_by_short_code(candidate)
            if existing is None:
                return candidate
            logger.debug(
                "Code collision on attempt %d/%d: %r",
                attempt + 1,
                _MAX_GENERATION_ATTEMPTS,
                candidate,
            )

        logger.error("Code generation exhausted after %d attempts.", _MAX_GENERATION_ATTEMPTS)
        raise CodeGenerationError(
            f"Failed to generate a unique short code after {_MAX_GENERATION_ATTEMPTS} attempts."
        )

    async def _safe_increment(self, short_code: str) -> None:
        try:
            await self._store.increment_access_count(short_code)
        except Exception as exc:
            logger.warning(
                "Failed to increment access count for short_code=%r: %s",
                short_code,
                exc,
            )
