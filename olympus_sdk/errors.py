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


# ============================================================================
# App-scoped permissions errors (olympus-cloud-gcp#3234 epic / #3254 issue)
# See docs/platform/APP-SCOPED-PERMISSIONS.md §6 + §17.7
# ============================================================================


class ConsentRequired(OlympusApiError):
    """Raised when a request targets a scope the user has not granted.

    Route the user to ``consent_url`` (when present) for the platform-served
    consent flow. After grant, retry the original call.
    """

    def __init__(
        self,
        *,
        scope: str,
        message: str,
        status_code: int = 403,
        request_id: str | None = None,
        consent_url: str | None = None,
    ) -> None:
        super().__init__(
            code="CONSENT_REQUIRED",
            message=message,
            status_code=status_code,
            request_id=request_id,
        )
        self.scope = scope
        self.consent_url = consent_url


class ScopeDenied(OlympusApiError):
    """Raised when scope IS granted but the bitset check still fails.

    Typically indicates a stale JWT from before a scope revoke. Callers
    should refresh the access token and retry once.
    """

    def __init__(
        self,
        *,
        scope: str,
        message: str,
        status_code: int = 403,
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            code="SCOPE_DENIED",
            message=message,
            status_code=status_code,
            request_id=request_id,
        )
        self.scope = scope


class BillingGraceExceeded(OlympusApiError):
    """Raised when entitlement grace policy blocks the requested action.

    ``grace_until`` is the timestamp after which lapsed state transitions
    to cancelled; ``upgrade_url`` links to the billing surface.
    """

    def __init__(
        self,
        *,
        message: str,
        status_code: int = 402,
        request_id: str | None = None,
        grace_until: str | None = None,
        upgrade_url: str | None = None,
    ) -> None:
        super().__init__(
            code="BILLING_GRACE_EXCEEDED",
            message=message,
            status_code=status_code,
            request_id=request_id,
        )
        self.grace_until = grace_until
        self.upgrade_url = upgrade_url


class DeviceChanged(OlympusApiError):
    """Raised when the platform requires a WebAuthn assertion on device change.

    ``challenge`` is the WebAuthn challenge to present to the authenticator;
    ``requires_reconsent`` is True when the triggering scope is destructive
    and an additional platform-served consent screen is also required.
    """

    def __init__(
        self,
        *,
        challenge: str,
        requires_reconsent: bool,
        message: str,
        status_code: int = 401,
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            code="DEVICE_CHANGED",
            message=message,
            status_code=status_code,
            request_id=request_id,
        )
        self.challenge = challenge
        self.requires_reconsent = requires_reconsent


class ExceptionRequestError(OlympusApiError):
    """Raised when a policy exception request is rejected (schema/rate-limit)."""

    def __init__(
        self,
        *,
        reason: str,
        message: str,
        status_code: int = 400,
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            code="EXCEPTION_REQUEST_INVALID",
            message=message,
            status_code=status_code,
            request_id=request_id,
        )
        self.reason = reason


class ExceptionExpired(OlympusApiError):
    """Raised when an approved exception has transitioned to the expired state.

    Consumers needing continued deviation MUST file a new exception
    (§17.5 — renewal is a new request, not a mutation).
    """

    def __init__(
        self,
        *,
        exception_id: str,
        message: str,
        status_code: int = 403,
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            code="EXCEPTION_EXPIRED",
            message=message,
            status_code=status_code,
            request_id=request_id,
        )
        self.exception_id = exception_id
