"""Models for the canonical ``/apps/*`` surface — the apps.install consent
ceremony shipped in olympus-cloud-gcp#3413 §3 (handlers + routes merged via
olympus-cloud-gcp#3422).

The ceremony has four states:

1. An app (via its SDK) calls :meth:`AppsService.install`. The server creates
   a pending-install row with a 10-minute TTL and returns a
   :class:`PendingInstall` carrying the unguessable ``pending_install_id``
   and the platform-served consent URL.
2. The app redirects the tenant_admin's browser to the consent URL. That
   surface calls ``GET /apps/pending_install/:id`` anonymously (the
   unguessable id IS the bearer) and gets back a
   :class:`PendingInstallDetail` with the eager-loaded :class:`AppManifest`
   for the consent screen's required-scope / optional-scope UI.
3. The tenant_admin clicks Approve (or Deny). The consent surface POSTs to
   ``/apps/pending_install/:id/approve`` (or ``/deny``) using the admin's
   session JWT. Approve returns the fresh :class:`AppInstall` row; Deny
   returns 204.
4. ``GET /apps/installed`` lists every active :class:`AppInstall` row for
   the current tenant. ``POST /apps/uninstall/:app_id`` soft-deletes —
   emits ``platform.app.uninstalled`` on Pub/Sub so the auth service
   consumer can kick session revocation for any JWT carrying that
   ``(tenant_id, app_id)`` pair (AC-7 follow-up — tracked on #3413).

All models are plain ``@dataclass`` types (no pydantic) for consistency with
every other model in :mod:`olympus_sdk.models`. Every shape carries a
``raw`` dict so callers can read unmodeled fields without forcing an SDK
bump every time the server adds a column.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# PendingInstall — POST /apps/install response
# ---------------------------------------------------------------------------


@dataclass
class PendingInstall:
    """Handle returned when an app initiates the install ceremony.

    The caller must redirect the tenant_admin to :attr:`consent_url` before
    :attr:`expires_at` (10 minutes after creation). Retrying the same
    ``(tenant_id, app_id, idempotency_key)`` within the window returns the
    original row — so losing a network round-trip on the mobile app and
    retrying does NOT create two pending rows.
    """

    #: Server-assigned UUID. Opaque to callers — treat as a pointer to the
    #: pending row, not a user-facing identifier.
    pending_install_id: str
    #: Platform-served consent URL. Carries the pending id in the path
    #: (``https://platform.olympuscloud.ai/apps/consent/<uuid>``). Apps MUST
    #: open this in a real browser tab (NOT an in-app webview) so the
    #: tenant_admin's authenticated cookie session is visible to the
    #: platform domain — a webview would present a fresh login prompt.
    consent_url: str
    #: Absolute ISO-8601 UTC expiry string. After this timestamp the consent
    #: URL returns 410 Gone and the caller must restart the ceremony with a
    #: fresh ``install(...)`` call.
    expires_at: str
    #: Full JSON response for unmodeled fields.
    raw: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> PendingInstall:
        return PendingInstall(
            pending_install_id=str(data.get("pending_install_id", "")),
            consent_url=str(data.get("consent_url", "")),
            expires_at=str(data.get("expires_at", "")),
            raw=dict(data),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "pending_install_id": self.pending_install_id,
            "consent_url": self.consent_url,
            "expires_at": self.expires_at,
        }


# ---------------------------------------------------------------------------
# AppManifest — GET /apps/manifest/:app_id + inline on pending detail
# ---------------------------------------------------------------------------


@dataclass
class AppManifest:
    """Versioned manifest row for an app in the platform catalog.

    Returned by ``GET /apps/manifest/:app_id`` (latest version) and
    eager-loaded onto :attr:`PendingInstallDetail.manifest` so the consent
    screen can render the required / optional scope checklists plus
    publisher / privacy / TOS links without a second round-trip.
    """

    #: Reverse-DNS app identifier (e.g. ``com.pizzaos``). Primary key against
    #: the ``app_manifests`` catalog.
    app_id: str
    #: Semver string (e.g. ``1.4.0``). The platform always serves the latest
    #: published row when multiple versions exist.
    version: str
    #: Human-facing app name for the consent screen header.
    name: str
    #: Human-facing publisher name (e.g. ``NëbusAI``, ``Acme Corp``).
    publisher: str
    #: Canonical scope strings the app CANNOT operate without. The consent
    #: screen renders these as required checkboxes — tenant_admin can only
    #: approve the install by granting the full set.
    scopes_required: list[str] = field(default_factory=list)
    #: Canonical scope strings the app can operate without but may request
    #: for enhanced functionality. Shown as opt-in checkboxes; the admin
    #: can toggle individual entries.
    scopes_optional: list[str] = field(default_factory=list)
    #: Optional URL to the app's square icon (typically CDN-hosted PNG/SVG).
    logo_url: str | None = None
    #: Optional URL to the app's privacy policy.
    privacy_url: str | None = None
    #: Optional URL to the app's terms of service.
    tos_url: str | None = None
    #: Full JSON response for unmodeled fields (screenshots, category tags,
    #: marketplace badges, etc.).
    raw: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> AppManifest:
        return AppManifest(
            app_id=str(data.get("app_id", "")),
            version=str(data.get("version", "")),
            name=str(data.get("name", "")),
            publisher=str(data.get("publisher", "")),
            scopes_required=[
                str(s) for s in (data.get("scopes_required") or []) if isinstance(s, str)
            ],
            scopes_optional=[
                str(s) for s in (data.get("scopes_optional") or []) if isinstance(s, str)
            ],
            logo_url=data.get("logo_url"),
            privacy_url=data.get("privacy_url"),
            tos_url=data.get("tos_url"),
            raw=dict(data),
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "app_id": self.app_id,
            "version": self.version,
            "name": self.name,
            "publisher": self.publisher,
            "scopes_required": list(self.scopes_required),
            "scopes_optional": list(self.scopes_optional),
        }
        if self.logo_url is not None:
            out["logo_url"] = self.logo_url
        if self.privacy_url is not None:
            out["privacy_url"] = self.privacy_url
        if self.tos_url is not None:
            out["tos_url"] = self.tos_url
        return out


# ---------------------------------------------------------------------------
# PendingInstallDetail — GET /apps/pending_install/:id (anonymous)
# ---------------------------------------------------------------------------


@dataclass
class PendingInstallDetail:
    """Full pending-install row, returned by ``GET /apps/pending_install/:id``.

    **Anonymous** — no JWT required. The unguessable id IS the bearer, and
    the row expires 10 minutes after creation. Rendered by the platform's
    consent surface (or, for whitelabeled tenants, by a tenant-owned
    consent shell) to drive the Approve / Deny buttons.

    :attr:`manifest` is eager-loaded server-side so the consent screen does
    NOT need to make a second ``getManifest`` round-trip. ``None`` is only
    possible in the unlikely event the manifest was delisted between create
    and read.

    :attr:`status` values: ``pending`` (active ceremony row) | ``approved``
    | ``denied``. Rows in a terminal state still return 200 (not 410) so
    the consent UI can show a clear "already approved / already denied"
    state instead of a generic expiry message.
    """

    id: str
    app_id: str
    tenant_id: str
    #: Scopes the app asked for on ``POST /apps/install`` — always a subset
    #: of :attr:`AppManifest.scopes_required` ∪
    #: :attr:`AppManifest.scopes_optional` at create time. Re-validated at
    #: approve time in case the manifest was updated.
    requested_scopes: list[str] = field(default_factory=list)
    #: Post-approval deep-link the app provided. The consent surface
    #: redirects the admin's browser here on Approve (or Deny — apps
    #: typically show a "cancelled" page on that path).
    return_to: str = ""
    #: ``pending`` | ``approved`` | ``denied``. Unknown strings surface
    #: verbatim — callers should gracefully handle server-side additions
    #: (e.g. ``expired`` if/when the sweeper starts writing terminal
    #: states).
    status: str = "pending"
    expires_at: str = ""
    #: Server-side eager-loaded manifest for the consent UI. ``None`` only
    #: in the rare case the manifest was delisted between create and read.
    manifest: AppManifest | None = None
    #: Full JSON response for unmodeled fields.
    raw: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> PendingInstallDetail:
        manifest_data = data.get("manifest")
        manifest: AppManifest | None = None
        if isinstance(manifest_data, dict):
            manifest = AppManifest.from_dict(manifest_data)
        return PendingInstallDetail(
            id=str(data.get("id", "")),
            app_id=str(data.get("app_id", "")),
            tenant_id=str(data.get("tenant_id", "")),
            requested_scopes=[
                str(s) for s in (data.get("requested_scopes") or []) if isinstance(s, str)
            ],
            return_to=str(data.get("return_to") or ""),
            status=str(data.get("status") or "pending"),
            expires_at=str(data.get("expires_at", "")),
            manifest=manifest,
            raw=dict(data),
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "app_id": self.app_id,
            "tenant_id": self.tenant_id,
            "requested_scopes": list(self.requested_scopes),
            "return_to": self.return_to,
            "status": self.status,
            "expires_at": self.expires_at,
        }
        if self.manifest is not None:
            out["manifest"] = self.manifest.to_dict()
        return out


# ---------------------------------------------------------------------------
# AppInstall — GET /apps/installed element + POST /approve response
# ---------------------------------------------------------------------------


@dataclass
class AppInstall:
    """Row from ``tenant_app_installs``.

    Returned by ``GET /apps/installed`` and as the result of
    ``POST /apps/pending_install/:id/approve``.

    This is the canonical ``AppInstall`` shape for the ``/apps/*``
    ceremony. The shorter 3-field shape returned inline by
    ``POST /tenant/create`` is the distinct
    :class:`~olympus_sdk.models.tenant.TenantAppInstall` in
    :mod:`olympus_sdk.models.tenant` — same family of data, different
    cardinality of fields.
    """

    tenant_id: str
    app_id: str
    installed_at: str
    #: User UUID of the tenant_admin who approved the install. On an install
    #: created via ``/tenant/create`` auto-install (where the user
    #: implicitly consents as part of signup) this is the newly-minted
    #: first admin's id.
    installed_by: str = ""
    #: Scopes granted at approval time. A subset of
    #: :attr:`AppManifest.scopes_required` ∪
    #: :attr:`AppManifest.scopes_optional` — the admin may have opted out
    #: of individual optional scopes.
    scopes_granted: list[str] = field(default_factory=list)
    #: ``active`` during normal operation; ``uninstalled`` after
    #: ``POST /apps/uninstall/:app_id``. Uninstalled rows remain in the
    #: listing briefly (ledger visibility) but are filtered out of
    #: ``listInstalled()`` by default on the server side.
    status: str = "active"
    #: Full JSON response for unmodeled fields (install_source, auto_renew,
    #: future billing column references, etc.).
    raw: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> AppInstall:
        return AppInstall(
            tenant_id=str(data.get("tenant_id", "")),
            app_id=str(data.get("app_id", "")),
            installed_at=str(data.get("installed_at", "")),
            installed_by=str(data.get("installed_by") or ""),
            scopes_granted=[
                str(s) for s in (data.get("scopes_granted") or []) if isinstance(s, str)
            ],
            status=str(data.get("status") or "active"),
            raw=dict(data),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "app_id": self.app_id,
            "installed_at": self.installed_at,
            "installed_by": self.installed_by,
            "scopes_granted": list(self.scopes_granted),
            "status": self.status,
        }


__all__ = [
    "AppInstall",
    "AppManifest",
    "PendingInstall",
    "PendingInstallDetail",
]
