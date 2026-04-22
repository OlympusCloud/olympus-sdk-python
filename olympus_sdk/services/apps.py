"""Apps ceremony — canonical ``/apps/*`` SDK surface (olympus-cloud-gcp#3413 §3).

Wraps the Rust platform service routes shipped in olympus-cloud-gcp#3422:

| Method | Route                                   | Auth                      |
|--------|-----------------------------------------|---------------------------|
| POST   | ``/apps/install``                       | tenant_admin + recent MFA |
| GET    | ``/apps/installed``                     | any tenant-scoped JWT     |
| POST   | ``/apps/uninstall/:app_id``             | tenant_admin + recent MFA |
| GET    | ``/apps/manifest/:app_id``              | any authenticated         |
| GET    | ``/apps/pending_install/:id``           | **anonymous**             |
| POST   | ``/apps/pending_install/:id/approve``   | tenant_admin              |
| POST   | ``/apps/pending_install/:id/deny``      | tenant_admin              |

Drives the four-state consent ceremony:

1. :meth:`AppsService.install` creates a pending-install row and returns
   :class:`~olympus_sdk.models.apps.PendingInstall` with a consent URL
   plus 10-minute TTL.
2. The consent UI fetches :meth:`AppsService.get_pending_install`
   anonymously (the unguessable id IS the bearer) to render the Approve /
   Deny screen.
3. tenant_admin approves via :meth:`AppsService.approve_pending_install`
   (returns the fresh :class:`~olympus_sdk.models.apps.AppInstall`) or
   denies via :meth:`AppsService.deny_pending_install`.
4. :meth:`AppsService.list_installed` / :meth:`AppsService.uninstall` /
   :meth:`AppsService.get_manifest` cover the steady-state app-management
   surface.

MFA gate (install / uninstall / approve): the tenant_admin's session must
carry a ``mfa_verified_at:<epoch>`` permission stamp within the last 10
minutes. If missing, the server returns 403 with ``mfa_required`` which
the SDK surfaces as :class:`~olympus_sdk.errors.OlympusApiError` — the
consumer is expected to trigger a step-up flow and retry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from olympus_sdk.models.apps import (
    AppInstall,
    AppManifest,
    PendingInstall,
    PendingInstallDetail,
)

if TYPE_CHECKING:
    from olympus_sdk.http import OlympusHttpClient


class AppsService:
    """Canonical ``/apps/*`` SDK surface.

    All methods are synchronous — the SDK's :class:`OlympusHttpClient` is
    built on ``httpx.Client`` and every other service in this SDK uses the
    same calling convention.
    """

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    # ------------------------------------------------------------------
    # POST /apps/install
    # ------------------------------------------------------------------

    def install(
        self,
        *,
        app_id: str,
        scopes: list[str],
        return_to: str,
        idempotency_key: str | None = None,
    ) -> PendingInstall:
        """Initiate the install ceremony for ``app_id``.

        Server creates a pending-install row, validates ``scopes`` against
        the latest :class:`AppManifest`, and returns a
        :class:`PendingInstall` with a consent URL the caller should open
        in a real browser tab (NOT an in-app webview — the consent screen
        needs the tenant_admin's authenticated cookie session on the
        platform domain).

        ``return_to`` is the post-approval deep-link the consent surface
        will redirect to on Approve (or Deny). Typically the app's
        "settings → permissions" screen so the admin lands back where they
        started.

        ``idempotency_key`` is optional. When supplied, retrying the same
        ``(tenant_id, app_id, idempotency_key)`` within the 10-minute
        pending window returns the ORIGINAL :class:`PendingInstall` rather
        than creating a second pending row. Use the calling user's device
        fingerprint or a UUID generated per "Install" button press to
        de-dupe retry noise without cross-user collisions.

        Requires tenant_admin role + recent MFA on the session. Raises
        :class:`~olympus_sdk.errors.OlympusApiError` on scope / manifest
        validation failures, missing MFA (403 ``mfa_required``), or an
        unknown ``app_id`` (404).
        """
        payload: dict[str, Any] = {
            "app_id": app_id,
            "scopes": list(scopes),
            "return_to": return_to,
        }
        if idempotency_key is not None:
            payload["idempotency_key"] = idempotency_key
        data = self._http.post("/apps/install", json=payload)
        return PendingInstall.from_dict(data)

    # ------------------------------------------------------------------
    # GET /apps/installed
    # ------------------------------------------------------------------

    def list_installed(self) -> list[AppInstall]:
        """List every app currently installed on the caller's tenant.

        Returns active installs only — :attr:`AppInstall.status` is
        ``active`` for each row. Uninstalled rows are filtered out
        server-side.

        Safe to call on any tenant-scoped JWT; no role requirement. The
        server may respond either with a raw JSON array or with an
        ``{"installs": [...]}`` envelope (depending on gateway shape);
        this method accepts both.
        """
        data = self._http.get("/apps/installed")
        rows: list[dict[str, Any]]
        if isinstance(data, list):
            rows = [r for r in data if isinstance(r, dict)]
        elif isinstance(data, dict) and isinstance(data.get("installs"), list):
            rows = [r for r in data["installs"] if isinstance(r, dict)]
        else:
            rows = []
        return [AppInstall.from_dict(r) for r in rows]

    # ------------------------------------------------------------------
    # POST /apps/uninstall/:app_id
    # ------------------------------------------------------------------

    def uninstall(self, app_id: str) -> None:
        """Uninstall ``app_id`` from the caller's tenant.

        Marks the install as ``uninstalled`` and emits
        ``platform.app.uninstalled`` on Pub/Sub. The auth service consumer
        for that event kicks session revocation for every JWT carrying
        this ``(tenant_id, app_id)`` pair — per AC-7 on #3413 the contract
        is 60-second session invalidation.

        Requires tenant_admin role + recent MFA. Raises
        :class:`~olympus_sdk.errors.OlympusApiError` on a tenant that
        doesn't have ``app_id`` installed (404) or a missing-MFA session
        (403 ``mfa_required``).
        """
        self._http.post(f"/apps/uninstall/{quote(app_id, safe='')}")

    # ------------------------------------------------------------------
    # GET /apps/manifest/:app_id
    # ------------------------------------------------------------------

    def get_manifest(self, app_id: str) -> AppManifest:
        """Fetch the latest published :class:`AppManifest` for ``app_id``.

        Useful for rendering "available apps" browsers outside the
        ceremony flow. Raises :class:`~olympus_sdk.errors.OlympusApiError`
        (404) if ``app_id`` has no manifest on the platform catalog.
        """
        data = self._http.get(f"/apps/manifest/{quote(app_id, safe='')}")
        return AppManifest.from_dict(data)

    # ------------------------------------------------------------------
    # GET /apps/pending_install/:id  (anonymous!)
    # ------------------------------------------------------------------

    def get_pending_install(self, pending_install_id: str) -> PendingInstallDetail:
        """Fetch the pending-install ceremony row by its unguessable id.

        **Anonymous — no JWT required.** The id is an unguessable UUID
        with a 10-minute TTL, issued by the server on :meth:`install`.
        The consent surface uses this call to render the Approve / Deny
        screen with eager-loaded
        :attr:`PendingInstallDetail.manifest` so no second round-trip is
        needed.

        Raises :class:`~olympus_sdk.errors.OlympusApiError` with
        ``status_code=410`` (Gone) if the pending row has expired or
        doesn't exist — the server masks "not found" as "gone" so an
        attacker can't enumerate ids.

        Safe to call with or without a session — the server ignores the
        ``Authorization`` header on this route. Note: the SDK will still
        attach the ``Authorization`` header if a session token is set on
        the HTTP client, but that is a no-op for the server.
        """
        data = self._http.get(
            f"/apps/pending_install/{quote(pending_install_id, safe='')}"
        )
        return PendingInstallDetail.from_dict(data)

    # ------------------------------------------------------------------
    # POST /apps/pending_install/:id/approve
    # ------------------------------------------------------------------

    def approve_pending_install(self, pending_install_id: str) -> AppInstall:
        """Approve a pending install.

        Server runs one Spanner transaction that resolves the pending row
        (``status=approved``) and upserts the ``tenant_app_installs`` row
        — returns the fresh :class:`AppInstall`. Also emits
        ``platform.app.installed`` on Pub/Sub for downstream consumers
        (billing activation, analytics, welcome email, etc.).

        Requires tenant_admin role on the TARGET tenant (the pending
        row's ``tenant_id``, which may differ from the session's
        ``tenant_id`` if an admin is completing consent on a device
        scoped to a different tenant) + a recent MFA stamp. Server
        re-validates the requested scopes against the latest manifest —
        if the manifest was updated to remove a scope between install and
        approve, the call fails with 400.

        Raises :class:`~olympus_sdk.errors.OlympusApiError`:

        - 410 (Gone) if the pending row expired between create and approve
        - 403 if caller is not a tenant_admin on the target tenant or MFA
          is stale
        - 400 if the pending row is already resolved (approved/denied)
        """
        data = self._http.post(
            f"/apps/pending_install/{quote(pending_install_id, safe='')}/approve"
        )
        return AppInstall.from_dict(data)

    # ------------------------------------------------------------------
    # POST /apps/pending_install/:id/deny
    # ------------------------------------------------------------------

    def deny_pending_install(self, pending_install_id: str) -> None:
        """Deny a pending install.

        Marks the pending row ``status=denied`` and emits
        ``platform.app.install_denied`` for analytics / funnel tracking.
        Returns 204 on success — there's no install record to surface on
        a deny.

        Requires tenant_admin role on the target tenant. Does NOT require
        fresh MFA — the deny path is idempotent and a deny-by-default is
        always safe.

        Raises :class:`~olympus_sdk.errors.OlympusApiError`:

        - 410 (Gone) if the pending row expired
        - 403 if caller is not a tenant_admin on the target tenant
        - 400 if the pending row is already resolved
        """
        self._http.post(
            f"/apps/pending_install/{quote(pending_install_id, safe='')}/deny"
        )


__all__ = ["AppsService"]
