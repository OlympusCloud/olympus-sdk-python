"""Tenant lifecycle — canonical ``/tenant/*`` SDK surface (#3403 §2 + §4.4).

Wraps the Rust platform service's tenant-lifecycle handlers shipped in
PR #3410. Replaces the raw ``INSERT INTO tenants`` hack that every app
(pizza-os, BarOS, OrderEchoAI, CallStackAI, Aura, Maximus-AI) had to
reinvent during onboarding.

Route map:

| Method | Route                    | Purpose                              |
|--------|--------------------------|--------------------------------------|
| POST   | ``/tenant/create``       | idempotent provision (24h key)       |
| GET    | ``/tenant/current``      | read active tenant                   |
| PATCH  | ``/tenant/current``      | update brand / plan / billing /etc.  |
| POST   | ``/tenant/retire``       | soft-delete + 30d grace (MFA + slug) |
| POST   | ``/tenant/unretire``     | within 30d grace                     |
| GET    | ``/tenant/mine``         | list tenants the caller can switch to|
| POST   | ``/tenant/switch``       | request cross-tenant session target  |
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from olympus_sdk.models.tenant import (
    ExchangedSession,
    Tenant,
    TenantOption,
    TenantProvisionResult,
    TenantUpdate,
)

if TYPE_CHECKING:
    from olympus_sdk.http import OlympusHttpClient
    from olympus_sdk.models.tenant import TenantFirstAdmin


class TenantService:
    """Canonical ``/tenant/*`` SDK surface.

    All methods are synchronous — the SDK's :class:`OlympusHttpClient` is
    built on ``httpx.Client`` and every other service uses the same
    calling convention.
    """

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create(
        self,
        *,
        brand_name: str,
        slug: str,
        plan: str,
        first_admin: TenantFirstAdmin,
        install_apps: list[str],
        idempotency_key: str,
        billing_address: str | None = None,
        tax_id: str | None = None,
    ) -> TenantProvisionResult:
        """Provision a new tenant.

        Idempotent: reusing ``idempotency_key`` within 24 hours returns the
        original ``TenantProvisionResult`` with ``idempotent=True``. Callers
        should use the Firebase UID (or any stable per-signup value) so a
        retried POST never creates a duplicate tenant.

        Validation errors (bad slug, unknown plan, invalid email) bubble as
        :class:`OlympusApiError` with a 422/400 status — map those to the
        signup wizard's inline-error UI.
        """
        payload: dict[str, Any] = {
            "brand_name": brand_name,
            "slug": slug,
            "plan": plan,
            "first_admin": first_admin.to_dict(),
            "install_apps": list(install_apps),
            "idempotency_key": idempotency_key,
        }
        if billing_address is not None:
            payload["billing_address"] = billing_address
        if tax_id is not None:
            payload["tax_id"] = tax_id
        data = self._http.post("/tenant/create", json=payload)
        return TenantProvisionResult.from_dict(data)

    # ------------------------------------------------------------------
    # Read / update
    # ------------------------------------------------------------------

    def current(self) -> Tenant:
        """Return the tenant the caller's JWT is scoped to."""
        data = self._http.get("/tenant/current")
        return Tenant.from_dict(data)

    def update(self, patch: TenantUpdate) -> Tenant:
        """Patch brand_name / plan / billing fields on the active tenant.

        Server merges the payload into existing ``settings`` so partial
        updates never clobber unrelated keys.
        """
        data = self._http.patch("/tenant/current", json=patch.to_dict())
        return Tenant.from_dict(data)

    # ------------------------------------------------------------------
    # Retire / unretire (§4.4)
    # ------------------------------------------------------------------

    def retire(self, *, confirmation_slug: str, reason: str | None = None) -> None:
        """Soft-delete the active tenant; 30-day grace window.

        Requires a tenant_admin JWT with recent MFA (≤10 min) and the
        ``confirmation_slug`` must match the tenant's slug exactly.
        Server returns 403 ``mfa_required`` when MFA is stale — prompt for
        step-up and retry.

        Fires ``platform.tenant.retired`` on Pub/Sub.
        """
        payload: dict[str, Any] = {"confirmation_slug": confirmation_slug}
        if reason is not None:
            payload["reason"] = reason
        self._http.post("/tenant/retire", json=payload)

    def unretire(self) -> None:
        """Reverse ``retire()`` within the 30-day grace window.

        Fires ``platform.tenant.unretired``. After 30d the server returns
        400 ``grace window expired`` — the tenant is then eligible for the
        background purge job.
        """
        self._http.post("/tenant/unretire")

    # ------------------------------------------------------------------
    # Multi-tenant navigation
    # ------------------------------------------------------------------

    def my_tenants(self) -> list[TenantOption]:
        """List the tenants the caller has an account in (same email)."""
        data = self._http.get("/tenant/mine")
        if isinstance(data, list):
            rows: list[dict[str, Any]] = data
        elif isinstance(data, dict) and isinstance(data.get("tenants"), list):
            rows = data["tenants"]
        else:
            rows = []
        return [TenantOption.from_dict(r) for r in rows if isinstance(r, dict)]

    def switch_tenant(self, tenant_id: str) -> ExchangedSession:
        """Request a session scoped to a different tenant.

        The platform endpoint only validates access and returns a redirect
        envelope naming ``/auth/switch-tenant`` as the actual session-mint
        target. This SDK method exposes both paths transparently: the
        returned :class:`ExchangedSession` carries the access token when
        the gateway has chosen to mint inline, otherwise it's empty and the
        caller should follow up with ``auth.switch_tenant()``.
        """
        data = self._http.post("/tenant/switch", json={"tenant_id": tenant_id})
        # The platform redirect envelope carries target_tenant_id +
        # auth_endpoint + instructions, not an access_token. Caller is
        # expected to POST to /auth/switch-tenant with its current
        # access_token to mint the new session. If the server ever changes
        # to mint inline, ExchangedSession.from_dict picks the tokens up.
        return ExchangedSession.from_dict(data if isinstance(data, dict) else None)


__all__ = ["TenantService"]
