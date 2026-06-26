"""Pydantic v2 schemas for the URL Shortener API.

Covers request/response contracts for all endpoints.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, field_validator, model_validator

# Maximum allowed value for expires_in (10 years in seconds)
_MAX_EXPIRES_IN = 315_576_000

# Pattern: alphanumeric characters and hyphens, length 3-50
_CUSTOM_CODE_PATTERN = re.compile(r'^[A-Za-z0-9\-]{3,50}$')


class ShortenRequest(BaseModel):
    """Request body for POST /shorten."""

    url: AnyHttpUrl
    custom_code: str | None = None
    expires_in: int | None = None  # seconds until expiration

    @field_validator("expires_in")
    @classmethod
    def validate_expires_in(cls, v: int | None) -> int | None:
        """Ensure expires_in is a positive integer no greater than 315,576,000."""
        if v is None:
            return v
        if v <= 0:
            raise ValueError("expires_in must be a positive integer")
        if v > _MAX_EXPIRES_IN:
            raise ValueError(
                f"expires_in must not exceed {_MAX_EXPIRES_IN} seconds (10 years)"
            )
        return v

    @field_validator("custom_code")
    @classmethod
    def validate_custom_code(cls, v: str | None) -> str | None:
        """Ensure custom_code contains only alphanumeric characters and hyphens,
        with a length between 3 and 50 characters."""
        if v is None:
            return v
        if not _CUSTOM_CODE_PATTERN.match(v):
            raise ValueError(
                "custom_code must contain only alphanumeric characters and hyphens "
                "and be between 3 and 50 characters long"
            )
        return v


class ShortenResponse(BaseModel):
    """Response body for POST /shorten."""

    short_url: str
    short_code: str
    original_url: str
    created_at: datetime
    expires_at: datetime | None = None


class StatsResponse(BaseModel):
    """Response body for GET /stats/{short_code}."""

    short_code: str
    original_url: str
    created_at: datetime  # ISO 8601
    access_count: int
    expires_at: datetime | None = None


class HealthResponse(BaseModel):
    """Response body for GET /health."""

    status: Literal["operational", "degraded"]
    store: Literal["reachable", "unreachable"]
