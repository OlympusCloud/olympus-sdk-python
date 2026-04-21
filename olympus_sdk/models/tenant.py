"""Tenant lifecycle and identity-invite models (olympus-cloud-gcp#3403 §2 + §4.2).

Mirrors the Rust request/response shapes on ``/tenant/*`` and
``/identity/invite*`` surfaces shipped in PR #3410.

All fields are snake_case to match the gateway JSON contract. These are
plain ``@dataclass`` types (no pydantic dep) for consistency with every
other model in ``olympus_sdk.models``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Shared / auth-adjacent shapes
# ---------------------------------------------------------------------------


@dataclass
class ExchangedSession:
    """Session-token bundle returned by tenant create / switch flows.

    On the create path the fields are ``None`` — the caller follows up with
    ``POST /auth/firebase/exchange`` (using the optional ``first_admin.firebase_link``)
    to mint a session. On the switch path the target ``/auth/switch-tenant``
    endpoint is what actually mints the new JWT; ``tenant/switch`` returns a
    redirect envelope the client is expected to post to.
    """

    access_token: str | None = None
    refresh_token: str | None = None
    access_expires_at: str | None = None

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> ExchangedSession:
        if not data:
            return ExchangedSession()
        return ExchangedSession(
            access_token=data.get("access_token"),
            refresh_token=data.get("refresh_token"),
            access_expires_at=data.get("access_expires_at"),
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.access_token is not None:
            out["access_token"] = self.access_token
        if self.refresh_token is not None:
            out["refresh_token"] = self.refresh_token
        if self.access_expires_at is not None:
            out["access_expires_at"] = self.access_expires_at
        return out


# ---------------------------------------------------------------------------
# /tenant/* shapes
# ---------------------------------------------------------------------------


@dataclass
class TenantFirstAdmin:
    """Initial-admin payload on ``POST /tenant/create``."""

    email: str
    first_name: str
    last_name: str
    #: Optional Firebase UID — links the caller's Firebase identity to the
    #: new tenant's first admin row.
    firebase_link: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
        }
        if self.firebase_link is not None:
            out["firebase_link"] = self.firebase_link
        return out


@dataclass
class AppInstall:
    """Record written to ``tenant_app_installs`` on ``POST /tenant/create``."""

    app_id: str
    status: str
    installed_at: str

    @staticmethod
    def from_dict(data: dict[str, Any]) -> AppInstall:
        return AppInstall(
            app_id=str(data.get("app_id", "")),
            status=str(data.get("status", "")),
            installed_at=str(data.get("installed_at", "")),
        )


@dataclass
class Tenant:
    """Canonical tenant record (mirrors ``platform::models::Tenant``).

    Not every field from the Rust struct is surfaced on day one — the ones
    below are the subset the gateway actually sends on ``/tenant/current``
    responses plus a generic ``raw`` stash for forward-compat consumers.
    """

    id: str
    slug: str
    name: str
    industry: str
    subscription_tier: str
    is_active: bool
    is_suspended: bool
    created_at: str
    updated_at: str
    legal_name: str | None = None
    parent_id: str | None = None
    path: str | None = None
    locale: str | None = None
    timezone: str | None = None
    billing_email: str | None = None
    stripe_customer_id: str | None = None
    stripe_connect_account_id: str | None = None
    trial_ends_at: str | None = None
    suspension_reason: str | None = None
    company_id: str | None = None
    deleted_at: str | None = None
    retired_at: str | None = None
    is_nebusai_company: bool = False
    settings: dict[str, Any] = field(default_factory=dict)
    features: dict[str, Any] = field(default_factory=dict)
    branding: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    #: Raw payload for forward-compat with platform columns the SDK hasn't
    #: codified yet — tests and consumers can dig into this when needed.
    raw: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Tenant:
        return Tenant(
            id=str(data.get("id", "")),
            slug=str(data.get("slug", "")),
            name=str(data.get("name", "")),
            industry=str(data.get("industry", "")),
            subscription_tier=str(data.get("subscription_tier", "")),
            is_active=bool(data.get("is_active", True)),
            is_suspended=bool(data.get("is_suspended", False)),
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
            legal_name=data.get("legal_name"),
            parent_id=data.get("parent_id"),
            path=data.get("path"),
            locale=data.get("locale"),
            timezone=data.get("timezone"),
            billing_email=data.get("billing_email"),
            stripe_customer_id=data.get("stripe_customer_id"),
            stripe_connect_account_id=data.get("stripe_connect_account_id"),
            trial_ends_at=data.get("trial_ends_at"),
            suspension_reason=data.get("suspension_reason"),
            company_id=data.get("company_id"),
            deleted_at=data.get("deleted_at"),
            retired_at=data.get("retired_at"),
            is_nebusai_company=bool(data.get("is_nebusai_company", False)),
            settings=dict(data.get("settings") or {}),
            features=dict(data.get("features") or {}),
            branding=dict(data.get("branding") or {}),
            metadata=dict(data.get("metadata") or {}),
            tags=list(data.get("tags") or []),
            raw=dict(data),
        )


@dataclass
class TenantProvisionResult:
    """Return shape from ``POST /tenant/create``."""

    tenant: Tenant
    admin_user_id: str
    session: ExchangedSession
    installed_apps: list[AppInstall]
    #: ``True`` when this is an idempotent retry (original create still in
    #: the 24-hour idempotency window).
    idempotent: bool

    @staticmethod
    def from_dict(data: dict[str, Any]) -> TenantProvisionResult:
        return TenantProvisionResult(
            tenant=Tenant.from_dict(dict(data.get("tenant") or {})),
            admin_user_id=str(data.get("admin_user_id", "")),
            session=ExchangedSession.from_dict(data.get("session") if isinstance(data.get("session"), dict) else None),
            installed_apps=[
                AppInstall.from_dict(a)
                for a in (data.get("installed_apps") or [])
                if isinstance(a, dict)
            ],
            idempotent=bool(data.get("idempotent", False)),
        )


@dataclass
class TenantUpdate:
    """Patch body for ``PATCH /tenant/current``.

    Every field is optional; unset fields are omitted from the wire payload
    so the server's merge-semantics stay intact.
    """

    brand_name: str | None = None
    plan: str | None = None
    billing_address: str | None = None
    tax_id: str | None = None
    locale: str | None = None
    timezone: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.brand_name is not None:
            out["brand_name"] = self.brand_name
        if self.plan is not None:
            out["plan"] = self.plan
        if self.billing_address is not None:
            out["billing_address"] = self.billing_address
        if self.tax_id is not None:
            out["tax_id"] = self.tax_id
        if self.locale is not None:
            out["locale"] = self.locale
        if self.timezone is not None:
            out["timezone"] = self.timezone
        return out


@dataclass
class TenantOption:
    """Row returned by ``GET /tenant/mine`` — a tenant the caller can switch into."""

    tenant_id: str
    slug: str
    name: str
    role: str | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> TenantOption:
        return TenantOption(
            tenant_id=str(data.get("tenant_id", "")),
            slug=str(data.get("slug", "")),
            name=str(data.get("name", "")),
            role=data.get("role"),
        )


# ---------------------------------------------------------------------------
# /identity/invite* shapes (§4.2)
# ---------------------------------------------------------------------------


@dataclass
class InviteHandle:
    """Single ``pending_invites`` row — return shape from invite create/list.

    ``token`` is only populated on the ``POST /identity/invite`` response.
    The server stores only a SHA-256 hash, so ``list`` / ``revoke`` never
    echo it back.
    """

    id: str
    email: str
    role: str
    tenant_id: str
    expires_at: str
    status: str
    created_at: str
    token: str | None = None
    location_id: str | None = None
    accepted_at: str | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> InviteHandle:
        return InviteHandle(
            id=str(data.get("id", "")),
            email=str(data.get("email", "")),
            role=str(data.get("role", "")),
            tenant_id=str(data.get("tenant_id", "")),
            expires_at=str(data.get("expires_at", "")),
            status=str(data.get("status", "")),
            created_at=str(data.get("created_at", "")),
            token=data.get("token"),
            location_id=data.get("location_id"),
            accepted_at=data.get("accepted_at"),
        )


__all__ = [
    "AppInstall",
    "ExchangedSession",
    "InviteHandle",
    "Tenant",
    "TenantFirstAdmin",
    "TenantOption",
    "TenantProvisionResult",
    "TenantUpdate",
]
