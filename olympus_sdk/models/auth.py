"""Auth models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class AuthSession:
    """Authenticated session returned after login or SSO."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600
    refresh_token: str | None = None
    user_id: str | None = None
    tenant_id: str | None = None
    roles: list[str] = field(default_factory=list)
    #: App-scoped permissions granted to this session (#3403 §1.2). Populated
    #: from the login response body and/or decoded from the JWT ``app_scopes``
    #: claim. Canonical strings like ``commerce.order.write@tenant``.
    app_scopes: list[str] = field(default_factory=list)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> AuthSession:
        roles_raw = data.get("roles")
        scopes_raw = data.get("app_scopes")
        return AuthSession(
            access_token=data["access_token"],
            token_type=data.get("token_type", "Bearer"),
            expires_in=data.get("expires_in", 3600),
            refresh_token=data.get("refresh_token"),
            user_id=data.get("user_id"),
            tenant_id=data.get("tenant_id"),
            roles=list(roles_raw) if roles_raw else [],
            app_scopes=list(scopes_raw) if scopes_raw else [],
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "access_token": self.access_token,
            "token_type": self.token_type,
            "expires_in": self.expires_in,
        }
        if self.refresh_token is not None:
            result["refresh_token"] = self.refresh_token
        if self.user_id is not None:
            result["user_id"] = self.user_id
        if self.tenant_id is not None:
            result["tenant_id"] = self.tenant_id
        if self.roles:
            result["roles"] = self.roles
        if self.app_scopes:
            result["app_scopes"] = self.app_scopes
        return result


@dataclass
class User:
    """A platform user."""

    id: str
    email: str
    name: str | None = None
    roles: list[str] = field(default_factory=list)
    tenant_id: str | None = None
    status: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> User:
        roles_raw = data.get("roles")
        return User(
            id=data["id"],
            email=data["email"],
            name=data.get("name"),
            roles=list(roles_raw) if roles_raw else [],
            tenant_id=data.get("tenant_id"),
            status=data.get("status"),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if data.get("created_at")
                else None
            ),
            updated_at=(
                datetime.fromisoformat(data["updated_at"])
                if data.get("updated_at")
                else None
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"id": self.id, "email": self.email}
        if self.name is not None:
            result["name"] = self.name
        if self.roles:
            result["roles"] = self.roles
        if self.tenant_id is not None:
            result["tenant_id"] = self.tenant_id
        if self.status is not None:
            result["status"] = self.status
        if self.created_at is not None:
            result["created_at"] = self.created_at.isoformat()
        if self.updated_at is not None:
            result["updated_at"] = self.updated_at.isoformat()
        return result


@dataclass
class ApiKey:
    """An API key for programmatic access."""

    id: str
    name: str
    key: str | None = None
    scopes: list[str] = field(default_factory=list)
    created_at: datetime | None = None
    expires_at: datetime | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> ApiKey:
        scopes_raw = data.get("scopes")
        return ApiKey(
            id=data["id"],
            name=data["name"],
            key=data.get("key"),
            scopes=list(scopes_raw) if scopes_raw else [],
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if data.get("created_at")
                else None
            ),
            expires_at=(
                datetime.fromisoformat(data["expires_at"])
                if data.get("expires_at")
                else None
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"id": self.id, "name": self.name}
        if self.key is not None:
            result["key"] = self.key
        if self.scopes:
            result["scopes"] = self.scopes
        if self.created_at is not None:
            result["created_at"] = self.created_at.isoformat()
        if self.expires_at is not None:
            result["expires_at"] = self.expires_at.isoformat()
        return result


# ---------------------------------------------------------------------------
# Firebase federation models (#3275 / #3473 fanout).
# Mirrors `backend/rust/auth/src/models.rs::LinkFirebaseResponse` and the
# 409 `multiple_tenants_match` candidate envelope returned by
# `services/identity_federation.rs::resolve_tenant_for_firebase`.
# ---------------------------------------------------------------------------


@dataclass
class FirebaseLinkResult:
    """Result of a successful ``POST /auth/firebase/link``.

    For idempotent re-link calls ``linked_at`` is the ORIGINAL timestamp
    the link was first established at, not "now".
    """

    olympus_id: str
    firebase_uid: str
    linked_at: datetime

    @staticmethod
    def from_dict(data: dict[str, Any]) -> FirebaseLinkResult:
        linked_at = data.get("linked_at")
        if isinstance(linked_at, datetime):
            ts = linked_at
        elif isinstance(linked_at, str):
            ts = datetime.fromisoformat(linked_at.replace("Z", "+00:00"))
        else:
            raise ValueError("linked_at missing or invalid in FirebaseLinkResult")
        return FirebaseLinkResult(
            olympus_id=str(data.get("olympus_id", "")),
            firebase_uid=str(data.get("firebase_uid", "")),
            linked_at=ts,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "olympus_id": self.olympus_id,
            "firebase_uid": self.firebase_uid,
            "linked_at": self.linked_at.isoformat(),
        }


@dataclass
class FirebaseTenantOption:
    """One candidate tenant returned in a ``409 multiple_tenants_match`` from
    ``/auth/firebase/exchange``.

    Named ``FirebaseTenantOption`` to avoid colliding with the pre-existing
    :class:`olympus_sdk.models.tenant.TenantOption`, which is the
    ``/tenant/mine`` projection (different shape).
    """

    tenant_id: str
    tenant_slug: str
    tenant_name: str

    @staticmethod
    def from_dict(data: dict[str, Any]) -> FirebaseTenantOption:
        return FirebaseTenantOption(
            tenant_id=str(data.get("tenant_id", "")),
            tenant_slug=str(data.get("tenant_slug", "")),
            tenant_name=str(data.get("tenant_name", "")),
        )
