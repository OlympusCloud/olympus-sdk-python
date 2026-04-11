"""Olympus SDK error types."""

from __future__ import annotations


class OlympusApiError(Exception):
    """Structured API error from Olympus Cloud.

    Raised when the server returns an error response with a JSON body
    containing ``error.code`` and ``error.message``.
    """

    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int = 0,
        request_id: str | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.request_id = request_id
        super().__init__(f"OlympusApiError({code}): {message} [status={status_code}]")

    def __repr__(self) -> str:
        return (
            f"OlympusApiError(code={self.code!r}, message={self.message!r}, "
            f"status_code={self.status_code}, request_id={self.request_id!r})"
        )


class OlympusNetworkError(Exception):
    """Raised when a network-level failure occurs (timeout, DNS, connection refused)."""

    def __init__(self, message: str, *, cause: BaseException | None = None) -> None:
        self.cause = cause
        super().__init__(message)

    def __repr__(self) -> str:
        return f"OlympusNetworkError({self.args[0]!r}, cause={self.cause!r})"
