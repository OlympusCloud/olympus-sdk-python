"""Authentication, user management, and API key operations.

Wraps the Olympus Auth service (Rust) via the Go API Gateway.
Routes: ``/auth/*``, ``/platform/users/*``.
"""

from __future__ import annotations

import base64
import json
from typing import TYPE_CHECKING

from olympus_sdk.errors import OlympusScopeRequiredError
from olympus_sdk.models.auth import ApiKey, AuthSession, User

if TYPE_CHECKING:
    from olympus_sdk.http import OlympusHttpClient


def _decode_jwt_app_scopes(access_token: str) -> list[str]:
    """Decode the ``app_scopes`` claim from an RS256/HS256 JWT payload.

    Returns an empty list if the token is malformed, unparseable, or the
    claim is absent / not a list of strings. No signature verification is
    performed — the SDK trusts the gateway's response.
    """
    parts = access_token.split(".")
    if len(parts) < 2:
        return []
    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload + padding)
        claims = json.loads(decoded.decode("utf-8"))
    except Exception:  # noqa: BLE001
        return []
    raw = claims.get("app_scopes") if isinstance(claims, dict) else None
    if not isinstance(raw, list):
        return []
    return [str(s) for s in raw if isinstance(s, str)]


class AuthService:
    """Authentication, user management, and API key operations."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http
        self._current_session: AuthSession | None = None

    # ------------------------------------------------------------------
    # Session accessors (#3403 §1.2)
    # ------------------------------------------------------------------

    @property
    def current_session(self) -> AuthSession | None:
        """The last :class:`AuthSession` returned by login/refresh, if any.

        Cleared by :meth:`logout`. External consumers that call
        :meth:`OlympusClient.set_access_token` directly do NOT populate this
        field — use the scope helpers on the client for those flows.
        """
        return self._current_session

    @property
    def granted_scopes(self) -> frozenset[str]:
        """All scopes granted to the current session.

        Pulled from :attr:`AuthSession.app_scopes`, which is populated from
        the login response body and/or decoded from the JWT ``app_scopes``
        claim. Returns an empty :class:`frozenset` when no session is active.
        """
        session = self._current_session
        if session is None:
            return frozenset()
        return frozenset(session.app_scopes or [])

    def has_scope(self, scope: str) -> bool:
        """Return ``True`` if the current session has the given scope.

        Fail-fast client-side check that runs before a network call. Prefer
        :class:`olympus_sdk.constants.OlympusScopes` typed constants over
        string literals.
        """
        return scope in self.granted_scopes

    def require_scope(self, scope: str) -> None:
        """Raise :class:`OlympusScopeRequiredError` if ``scope`` is not granted.

        Used to assert a scope client-side before attempting a write that
        would otherwise round-trip only to be rejected with a
        ``scope_not_granted`` error from the gateway.
        """
        if not self.has_scope(scope):
            raise OlympusScopeRequiredError(scope)

    # ------------------------------------------------------------------
    # Login / session lifecycle
    # ------------------------------------------------------------------

    def _capture_session(self, session: AuthSession) -> AuthSession:
        """Populate ``app_scopes`` from JWT when response body didn't, stash."""
        if not session.app_scopes:
            decoded = _decode_jwt_app_scopes(session.access_token)
            if decoded:
                session.app_scopes = decoded
        self._current_session = session
        return session

    def login(self, email: str, password: str) -> AuthSession:
        """Authenticate with email and password.

        On success the returned access token is automatically set on the
        HTTP client for subsequent requests.
        """
        data = self._http.post("/auth/login", json={"email": email, "password": password})
        session = AuthSession.from_dict(data)
        self._http.set_access_token(session.access_token)
        return self._capture_session(session)

    def login_sso(self, provider: str) -> AuthSession:
        """Initiate SSO login via an external provider (e.g. "google", "apple")."""
        data = self._http.post("/auth/sso/initiate", json={"provider": provider})
        session = AuthSession.from_dict(data)
        self._http.set_access_token(session.access_token)
        return self._capture_session(session)

    def login_pin(self, pin: str, *, location_id: str | None = None) -> AuthSession:
        """Authenticate staff using a PIN code."""
        payload: dict[str, str] = {"pin": pin}
        if location_id is not None:
            payload["location_id"] = location_id
        data = self._http.post("/auth/login/pin", json=payload)
        session = AuthSession.from_dict(data)
        self._http.set_access_token(session.access_token)
        return self._capture_session(session)

    def me(self) -> User:
        """Get the currently authenticated user profile."""
        data = self._http.get("/auth/me")
        return User.from_dict(data)

    def refresh(self, refresh_token: str) -> AuthSession:
        """Refresh the access token using a refresh token."""
        data = self._http.post("/auth/refresh", json={"refresh_token": refresh_token})
        session = AuthSession.from_dict(data)
        self._http.set_access_token(session.access_token)
        return self._capture_session(session)

    def logout(self) -> None:
        """Log out the current session."""
        self._http.post("/auth/logout")
        self._http.clear_access_token()
        self._current_session = None

    def create_user(
        self,
        *,
        name: str,
        email: str,
        role: str,
        password: str | None = None,
    ) -> User:
        """Create a new user on the platform."""
        payload: dict[str, str] = {"name": name, "email": email, "role": role}
        if password is not None:
            payload["password"] = password
        data = self._http.post("/platform/users", json=payload)
        return User.from_dict(data)

    def assign_role(self, user_id: str, role: str) -> None:
        """Assign a role to a user."""
        self._http.post(f"/platform/users/{user_id}/roles", json={"role": role})

    def check_permission(self, user_id: str, permission: str) -> bool:
        """Check whether a user has a specific permission."""
        data = self._http.get(
            f"/platform/users/{user_id}/permissions/check",
            params={"permission": permission},
        )
        return bool(data.get("allowed", False))

    def create_api_key(self, name: str, scopes: list[str]) -> ApiKey:
        """Create a new API key for programmatic access."""
        data = self._http.post(
            "/platform/tenants/me/api-keys",
            json={"name": name, "scopes": scopes},
        )
        return ApiKey.from_dict(data)

    def revoke_api_key(self, key_id: str) -> None:
        """Revoke an existing API key."""
        self._http.delete(f"/platform/tenants/me/api-keys/{key_id}")
