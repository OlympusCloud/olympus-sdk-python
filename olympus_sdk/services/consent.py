"""ConsentService — app-scoped permissions.

olympus-cloud-gcp#3254 for the Python SDK. Surface matches §6 of
docs/platform/APP-SCOPED-PERMISSIONS.md. Every method hits a platform
endpoint; no client-side state.

The ``has_scope_bit`` fast path lives on ``OlympusClient`` directly
(constant-time bitmask against the decoded JWT bitset). This service is
for server-side grant mutations and scope introspection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import quote

from olympus_sdk.http import OlympusHttpClient

Holder = Literal["tenant", "user"]
GrantSource = Literal["install", "admin_ui", "scope_upgrade", "migration"]


@dataclass
class ConsentPrompt:
    """Server-rendered consent prompt with stable hash for audit."""

    scope: str
    description: str
    consent_copy: str
    prompt_hash: str
    is_destructive: bool
    requires_mfa: bool


@dataclass
class Grant:
    """A grant row from platform_app_tenant_grants or platform_app_user_grants."""

    tenant_id: str
    app_id: str
    scope: str
    granted_at: str
    source: GrantSource
    granted_by: str | None = None
    user_id: str | None = None
    revoked_at: str | None = None


class ConsentService:
    """Consent surface for tenant-admin and end-user scope grants."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    def list_granted(
        self,
        *,
        app_id: str,
        tenant_id: str | None = None,
        holder: Holder = "tenant",
    ) -> list[Grant]:
        """List active (non-revoked) scope grants for an app.

        Defaults to tenant-scoped grants; pass ``holder="user"`` for the
        caller's own user grants.
        """
        path_suffix = "tenant-grants" if holder == "tenant" else "user-grants"
        path = f"/api/v1/platform/apps/{quote(app_id, safe='')}/{path_suffix}"
        params: dict[str, str] = {}
        if tenant_id is not None:
            params["tenant_id"] = tenant_id
        body = self._http.get(path, params=params)
        rows = body.get("grants", []) or []
        return [_to_grant(row) for row in rows]

    def describe(self, *, app_id: str, scope: str) -> ConsentPrompt:
        """Fetch the consent prompt + hash for a scope.

        Call BEFORE ``grant(scope, ..., prompt_hash=...)`` so the returned
        ``prompt_hash`` can be sent back as proof of what the user saw.
        """
        body = self._http.get(
            "/api/v1/platform/consent-prompt",
            params={"app_id": app_id, "scope": scope},
        )
        return ConsentPrompt(
            scope=body.get("scope", ""),
            description=body.get("description", ""),
            consent_copy=body.get("consent_copy", ""),
            prompt_hash=body.get("prompt_hash", ""),
            is_destructive=bool(body.get("is_destructive", False)),
            requires_mfa=bool(body.get("requires_mfa", False)),
        )

    def grant(
        self,
        *,
        app_id: str,
        scope: str,
        holder: Holder,
        tenant_id: str | None = None,
        user_id: str | None = None,
        prompt_hash: str | None = None,
    ) -> Grant:
        """Grant a scope.

        Tenant scopes require ``tenant_admin`` role; user scopes require the
        caller's own JWT. For ``holder="user"``, ``prompt_hash`` MUST match
        the server's current consent copy (fetched via ``describe``).
        """
        path_suffix = "tenant-grants" if holder == "tenant" else "user-grants"
        path = f"/api/v1/platform/apps/{quote(app_id, safe='')}/{path_suffix}"
        payload: dict[str, Any] = {"scope": scope}
        if tenant_id is not None:
            payload["tenant_id"] = tenant_id
        if user_id is not None:
            payload["user_id"] = user_id
        if prompt_hash is not None:
            payload["consent_prompt_hash"] = prompt_hash
        body = self._http.post(path, json=payload)
        return _to_grant(body)

    def revoke(self, *, app_id: str, scope: str, holder: Holder) -> None:
        """Revoke a scope (soft delete — sets ``revoked_at``)."""
        path_suffix = "tenant-grants" if holder == "tenant" else "user-grants"
        path = (
            f"/api/v1/platform/apps/{quote(app_id, safe='')}/{path_suffix}/"
            f"{quote(scope, safe='')}"
        )
        self._http.delete(path)


def _to_grant(row: dict[str, Any]) -> Grant:
    return Grant(
        tenant_id=row.get("tenant_id", ""),
        app_id=row.get("app_id", ""),
        scope=row.get("scope", ""),
        granted_at=row.get("granted_at", ""),
        granted_by=row.get("granted_by"),
        user_id=row.get("user_id"),
        source=row.get("source", "install"),
        revoked_at=row.get("revoked_at"),
    )
