"""Short code generator for the URL Shortener service.

Uses cryptographically secure randomness to produce alphanumeric codes.
"""

from __future__ import annotations

import secrets
import string


class CodeGenerator:
    """Generates random alphanumeric short codes.

    Uses `secrets.choice` for cryptographic randomness so that
    generated codes are unpredictable.

    Attributes:
        ALPHABET: The character set used when generating codes -- all
                  ASCII letters (upper and lower case) plus digits 0-9.
    """

    ALPHABET: str = string.ascii_letters + string.digits  # A-Z a-z 0-9

    def generate(self, length: int = 8) -> str:
        """Return a random alphanumeric string of the given length.

        Args:
            length: Number of characters in the returned code.
                    Must be between 6 and 12 inclusive.

        Returns:
            A random string composed solely of characters from ALPHABET.

        Raises:
            ValueError: If length is outside the accepted range [6, 12].
        """
        if length < 6 or length > 12:
            raise ValueError(
                "length must be between 6 and 12 inclusive, got " + str(length)
            )
        return "".join(secrets.choice(self.ALPHABET) for _ in range(length))