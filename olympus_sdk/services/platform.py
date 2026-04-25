"""Platform-level catalog reads — scope registry + digest (#3517).

Wraps the Rust platform service's catalog-read endpoints landed in
olympus-cloud-gcp PR #3517. These are platform-wide reads (not tenant-
scoped); tenant-lifecycle workflows live on :class:`TenantService` instead.

Routes:

| Method | Route                              | Purpose                              |
|--------|------------------------------------|--------------------------------------|
| GET    | ``/platform/scope-registry``       | list seeded scope catalog rows       |
| GET    | ``/platform/scope-registry/digest``| deterministic platform catalog digest|

Auth: any authenticated tenant user (catalog data is non-secret).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from olympus_sdk.http import OlympusHttpClient


@dataclass
class ScopeRow:
    """One row of the platform scope registry (#3517).

    ``bit_id`` is ``None`` when the scope hasn't been allocated a bit yet
    (workshop_status pre-``service_ok``). Pre-allocation rows can still
    appear in authoring views so the developer-portal picker stays useful
    before a scope graduates.
    """

    scope: str
    resource: str
    action: str
    holder: str
    namespace: str
    description: str
    is_destructive: bool
    requires_mfa: bool
    grace_behavior: str
    consent_prompt_copy: str
    workshop_status: str
    owner_app_id: str | None = None
    bit_id: int | None = None


@dataclass
class ScopeRegistryListing:
    """Result of :meth:`PlatformService.list_scope_registry`."""

    scopes: list[ScopeRow] = field(default_factory=list)
    total: int = 0


@dataclass
class ScopeRegistryDigest:
    """Result of :meth:`PlatformService.get_scope_registry_digest`.

    ``platform_catalog_digest`` is the SHA-256 hex over
    ``(bit_id, scope, status)`` rows of the platform-tier registry,
    matching ``scripts/seed_platform_scopes.py:platform_catalog_digest()``
    byte-for-byte. JWT mints embed this value so the gateway middleware
    can detect stale tokens after a catalog rotation.
    """

    platform_catalog_digest: str = ""
    row_count: int = 0


def _opt_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _to_scope_row(row: dict[str, Any]) -> ScopeRow:
    bit_id_raw = row.get("bit_id")
    bit_id = bit_id_raw if isinstance(bit_id_raw, int) else None
    return ScopeRow(
        scope=row.get("scope", "") or "",
        resource=row.get("resource", "") or "",
        action=row.get("action", "") or "",
        holder=row.get("holder", "") or "",
        namespace=row.get("namespace", "") or "",
        description=row.get("description", "") or "",
        is_destructive=bool(row.get("is_destructive", False)),
        requires_mfa=bool(row.get("requires_mfa", False)),
        grace_behavior=row.get("grace_behavior", "") or "",
        consent_prompt_copy=row.get("consent_prompt_copy", "") or "",
        workshop_status=row.get("workshop_status", "") or "",
        owner_app_id=_opt_str(row.get("owner_app_id")),
        bit_id=bit_id,
    )


def _to_scope_registry_listing(row: dict[str, Any]) -> ScopeRegistryListing:
    scopes_raw = row.get("scopes") or []
    scopes = [
        _to_scope_row(s) for s in scopes_raw if isinstance(s, dict)
    ]
    total_raw = row.get("total")
    total = total_raw if isinstance(total_raw, int) else 0
    return ScopeRegistryListing(scopes=scopes, total=total)


def _to_scope_registry_digest(row: dict[str, Any]) -> ScopeRegistryDigest:
    digest_raw = row.get("platform_catalog_digest")
    count_raw = row.get("row_count")
    return ScopeRegistryDigest(
        platform_catalog_digest=digest_raw if isinstance(digest_raw, str) else "",
        row_count=count_raw if isinstance(count_raw, int) else 0,
    )


class PlatformService:
    """Platform-level catalog reads — scope registry + digest (#3517)."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    def list_scope_registry(
        self,
        *,
        namespace: str | None = None,
        owner_app_id: str | None = None,
        include_drafts: bool = False,
    ) -> ScopeRegistryListing:
        """List the seeded scope catalog (#3517).

        Optional filters:

        - ``namespace``: filter to one namespace (e.g. ``voice``, ``platform``).
        - ``owner_app_id``: filter by owning app id. Pass empty string
          (``""``) for platform-owned scopes only — semantically distinct
          from omitting the parameter (which means "no filter").
        - ``include_drafts``: include rows still in pre-``service_ok``
          workshop status. Default ``False`` returns only the published
          surface (workshop_status in ``service_ok | legal_ok | approved``).
        """
        params: dict[str, Any] = {}
        if namespace is not None:
            params["namespace"] = namespace
        if owner_app_id is not None:
            params["owner_app_id"] = owner_app_id
        if include_drafts:
            params["include_drafts"] = "true"
        data = self._http.get(
            "/platform/scope-registry",
            params=params if params else None,
        )
        return _to_scope_registry_listing(data)

    def get_scope_registry_digest(self) -> ScopeRegistryDigest:
        """Fetch the deterministic platform catalog digest (#3517).

        Returns sha256 over ``(bit_id, scope, status)`` rows of the
        platform-tier registry (matches Python seed-script output
        byte-for-byte). Read-only, no Spanner shell required.
        """
        data = self._http.get("/platform/scope-registry/digest")
        return _to_scope_registry_digest(data)
