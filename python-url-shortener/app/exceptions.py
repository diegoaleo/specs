"""Exception hierarchy for the URL Shortener service.

All application errors derive from AppError so that a single FastAPI
exception handler can catch and format them consistently.
"""


class AppError(Exception):
    """Base class for all application-specific errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return self.message


class ValidationError(AppError):
    """Raised when request input fails validation rules.

    Maps to HTTP 422 Unprocessable Entity.
    """


class NotFoundError(AppError):
    """Raised when a requested resource (e.g. short code) does not exist.

    Maps to HTTP 404 Not Found.
    """


class ConflictError(AppError):
    """Raised when a custom short code is already in use.

    Maps to HTTP 409 Conflict.
    """


class ExpiredError(AppError):
    """Raised when a short code exists but its expiration time has passed.

    Maps to HTTP 410 Gone.
    """


class StorageError(AppError):
    """Raised when the store is unreachable or cannot be read from.

    Maps to HTTP 503 Service Unavailable.
    """


class StorageWriteError(AppError):
    """Raised when a write operation to the store fails.

    Maps to HTTP 500 Internal Server Error.
    """


class CodeGenerationError(AppError):
    """Raised when the code generator fails to produce a unique code
    after the maximum number of retry attempts (10).

    Maps to HTTP 500 Internal Server Error.
    """
