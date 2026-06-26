"""Unit tests for Pydantic schema validation.

Covers ShortenRequest validation for task 2.2.
Requirements: 1.3, 1.4, 5.2, 5.4, 6.4
"""

import pytest
from pydantic import ValidationError

from app.schemas.url import ShortenRequest


class TestShortenRequestValidUrl:
    """Tests for valid ShortenRequest inputs."""

    def test_valid_http_url(self):
        """A valid HTTP URL with no optional fields should pass validation."""
        req = ShortenRequest(url="http://example.com")
        assert str(req.url) in ("http://example.com/", "http://example.com")

    def test_valid_https_url(self):
        """A valid HTTPS URL should pass validation."""
        req = ShortenRequest(url="https://example.com/path?q=1")
        assert req.url is not None

    def test_valid_url_with_custom_code(self):
        """A valid URL with a valid custom_code should pass."""
        req = ShortenRequest(url="https://example.com", custom_code="my-link")
        assert req.custom_code == "my-link"

    def test_valid_url_with_expires_in(self):
        """A valid URL with a valid expires_in should pass."""
        req = ShortenRequest(url="https://example.com", expires_in=3600)
        assert req.expires_in == 3600

    def test_valid_url_all_fields(self):
        """A valid URL with all fields provided should pass."""
        req = ShortenRequest(
            url="https://example.com",
            custom_code="abc",
            expires_in=60,
        )
        assert req.custom_code == "abc"
        assert req.expires_in == 60

    def test_optional_fields_default_to_none(self):
        """custom_code and expires_in should default to None when omitted."""
        req = ShortenRequest(url="https://example.com")
        assert req.custom_code is None
        assert req.expires_in is None

    def test_expires_in_max_boundary(self):
        """expires_in equal to 315,576,000 should be accepted."""
        req = ShortenRequest(url="https://example.com", expires_in=315_576_000)
        assert req.expires_in == 315_576_000

    def test_expires_in_min_boundary(self):
        """expires_in equal to 1 should be accepted."""
        req = ShortenRequest(url="https://example.com", expires_in=1)
        assert req.expires_in == 1

    def test_custom_code_min_length(self):
        """custom_code of exactly 3 characters should be accepted."""
        req = ShortenRequest(url="https://example.com", custom_code="abc")
        assert req.custom_code == "abc"

    def test_custom_code_max_length(self):
        """custom_code of exactly 50 characters should be accepted."""
        code = "a" * 50
        req = ShortenRequest(url="https://example.com", custom_code=code)
        assert req.custom_code == code

    def test_custom_code_with_hyphens(self):
        """custom_code containing hyphens should be accepted."""
        req = ShortenRequest(url="https://example.com", custom_code="my-short-code")
        assert req.custom_code == "my-short-code"

    def test_custom_code_alphanumeric(self):
        """custom_code with mixed alphanumerics should be accepted."""
        req = ShortenRequest(url="https://example.com", custom_code="ABC123")
        assert req.custom_code == "ABC123"


class TestShortenRequestMissingUrl:
    """Tests that missing url field raises ValidationError."""

    def test_missing_url_raises_422(self):
        """Omitting the required `url` field should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ShortenRequest()
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("url",) for e in errors)

    def test_missing_url_error_type(self):
        """The error for missing url should be a missing field error."""
        with pytest.raises(ValidationError) as exc_info:
            ShortenRequest()
        errors = exc_info.value.errors()
        url_errors = [e for e in errors if e["loc"] == ("url",)]
        assert len(url_errors) == 1
        assert url_errors[0]["type"] == "missing"


class TestShortenRequestInvalidScheme:
    """Tests that non-http/https URL schemes raise ValidationError."""

    def test_ftp_scheme_raises_422(self):
        """A URL with ftp:// scheme should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ShortenRequest(url="ftp://example.com/file.txt")
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("url",) for e in errors)

    def test_file_scheme_raises_422(self):
        """A URL with file:// scheme should raise ValidationError."""
        with pytest.raises(ValidationError):
            ShortenRequest(url="file:///etc/passwd")

    def test_plain_string_raises_422(self):
        """A plain string that is not a URL should raise ValidationError."""
        with pytest.raises(ValidationError):
            ShortenRequest(url="not-a-url")


class TestShortenRequestCustomCodeValidation:
    """Tests for custom_code field validation."""

    def test_whitespace_custom_code_raises_422(self):
        """A custom_code of only whitespace should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ShortenRequest(url="https://example.com", custom_code="   ")
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("custom_code",) for e in errors)

    def test_custom_code_with_special_chars_raises_422(self):
        """A custom_code containing special characters should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ShortenRequest(url="https://example.com", custom_code="bad@code!")
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("custom_code",) for e in errors)

    def test_custom_code_with_underscore_raises_422(self):
        """A custom_code containing an underscore should raise ValidationError."""
        with pytest.raises(ValidationError):
            ShortenRequest(url="https://example.com", custom_code="bad_code")

    def test_custom_code_2_chars_raises_422(self):
        """A custom_code of only 2 characters (below minimum length) should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ShortenRequest(url="https://example.com", custom_code="ab")
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("custom_code",) for e in errors)

    def test_custom_code_51_chars_raises_422(self):
        """A custom_code of 51 characters (above maximum length) should raise ValidationError."""
        long_code = "a" * 51
        with pytest.raises(ValidationError) as exc_info:
            ShortenRequest(url="https://example.com", custom_code=long_code)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("custom_code",) for e in errors)

    def test_custom_code_empty_string_raises_422(self):
        """An empty string custom_code should raise ValidationError."""
        with pytest.raises(ValidationError):
            ShortenRequest(url="https://example.com", custom_code="")

    def test_custom_code_1_char_raises_422(self):
        """A custom_code of only 1 character should raise ValidationError."""
        with pytest.raises(ValidationError):
            ShortenRequest(url="https://example.com", custom_code="a")


class TestShortenRequestExpiresInValidation:
    """Tests for expires_in field validation."""

    def test_expires_in_zero_raises_422(self):
        """expires_in=0 should raise ValidationError (must be positive)."""
        with pytest.raises(ValidationError) as exc_info:
            ShortenRequest(url="https://example.com", expires_in=0)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("expires_in",) for e in errors)

    def test_expires_in_negative_raises_422(self):
        """A negative expires_in should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ShortenRequest(url="https://example.com", expires_in=-1)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("expires_in",) for e in errors)

    def test_expires_in_over_max_raises_422(self):
        """expires_in=315,576,001 (above max) should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ShortenRequest(url="https://example.com", expires_in=315_576_001)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("expires_in",) for e in errors)

    def test_expires_in_large_value_raises_422(self):
        """A very large expires_in should raise ValidationError."""
        with pytest.raises(ValidationError):
            ShortenRequest(url="https://example.com", expires_in=999_999_999)

    def test_expires_in_none_is_valid(self):
        """expires_in=None (explicit) should pass validation."""
        req = ShortenRequest(url="https://example.com", expires_in=None)
        assert req.expires_in is None
