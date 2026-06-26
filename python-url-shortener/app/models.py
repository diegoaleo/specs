"""Domain model for the URL Shortener service."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Mapping:
    """Represents a persisted association between a short code and an original URL.

    Attributes:
        short_code:   The unique short identifier (e.g. "abc123").
        original_url: The fully-qualified original URL the code redirects to.
        created_at:   UTC timestamp when this mapping was created.
        access_count: Number of times this mapping has been resolved via redirect.
        expires_at:   Optional UTC timestamp after which the mapping is considered
                      expired.  ``None`` means the mapping never expires.
    """

    short_code: str
    original_url: str
    created_at: datetime
    access_count: int = field(default=0)
    expires_at: datetime | None = field(default=None)

    def is_expired(self) -> bool:
        """Return True if this mapping has an expiration time that is in the past.

        The comparison is performed using UTC time.  A mapping with
        ``expires_at=None`` never expires and this method returns False.

        Returns:
            bool: True when ``expires_at`` is set and the current UTC time is
                  strictly greater than ``expires_at``; False otherwise.
        """
        if self.expires_at is None:
            return False
        now = datetime.now(timezone.utc)
        # Normalise expires_at to an aware datetime if it was stored as naive UTC.
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return now > expires
