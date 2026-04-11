"""Authentication, user management, and API key operations.

Wraps the Olympus Auth service (Rust) via the Go API Gateway.
Routes: ``/auth/*``, ``/platform/users/*``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from olympus_sdk.models.auth import ApiKey, AuthSession, User

if TYPE_CHECKING:
    from olympus_sdk.http import OlympusHttpClient


class AuthService:
    """Authentication, user management, and API key operations."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    def login(self, email: str, password: str) -> AuthSession:
        """Authenticate with email and password.

        On success the returned access token is automatically set on the
        HTTP client for subsequent requests.
        """
        data = self._http.post("/auth/login", json={"email": email, "password": password})
        session = AuthSession.from_dict(data)
        self._http.set_access_token(session.access_token)
        return session

    def login_sso(self, provider: str) -> AuthSession:
        """Initiate SSO login via an external provider (e.g. "google", "apple")."""
        data = self._http.post("/auth/sso/initiate", json={"provider": provider})
        session = AuthSession.from_dict(data)
        self._http.set_access_token(session.access_token)
        return session

    def login_pin(self, pin: str, *, location_id: str | None = None) -> AuthSession:
        """Authenticate staff using a PIN code."""
        payload: dict[str, str] = {"pin": pin}
        if location_id is not None:
            payload["location_id"] = location_id
        data = self._http.post("/auth/login/pin", json=payload)
        session = AuthSession.from_dict(data)
        self._http.set_access_token(session.access_token)
        return session

    def me(self) -> User:
        """Get the currently authenticated user profile."""
        data = self._http.get("/auth/me")
        return User.from_dict(data)

    def refresh(self, refresh_token: str) -> AuthSession:
        """Refresh the access token using a refresh token."""
        data = self._http.post("/auth/refresh", json={"refresh_token": refresh_token})
        session = AuthSession.from_dict(data)
        self._http.set_access_token(session.access_token)
        return session

    def logout(self) -> None:
        """Log out the current session."""
        self._http.post("/auth/logout")
        self._http.clear_access_token()

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
