"""Olympus ID — global, cross-tenant identity & federation.

Wraps the Olympus Platform service (Rust) Identity handler via the Go API
Gateway. Routes:

- ``POST /api/v1/platform/identities``       — get-or-create identity
- ``POST /api/v1/platform/identities/links`` — link identity to a tenant
- ``POST /api/v1/identity/scan-id``          — Document-AI age verification (#3009)
- ``GET  /api/v1/identity/status/{phone}``   — verification status
- ``POST /api/v1/identity/verify-passphrase``
- ``POST /api/v1/identity/set-passphrase``
- ``POST /api/v1/identity/create-upload-session``
- ``POST /api/v1/identity/invite``                          — invite staff/manager (#3403 §4.2)
- ``GET  /api/v1/identity/invites``
- ``POST /api/v1/identity/invites/{token}/accept``
- ``POST /api/v1/identity/invites/{id}/revoke``
- ``POST /api/v1/identity/remove_from_tenant``              — §4.4

An :class:`OlympusIdentity` is keyed by Firebase UID and represents one
human across every Olympus Cloud app. Call
:meth:`get_or_create_from_firebase` right after a successful Firebase
sign-in to materialize the global identity, then :meth:`link_to_tenant`
when the user first transacts with a tenant so the global identity can be
cross-referenced with the tenant's commerce customer.
"""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from olympus_sdk.models.identity import OlympusIdentity
from olympus_sdk.models.tenant import InviteHandle

if TYPE_CHECKING:
    from olympus_sdk.http import OlympusHttpClient


class IdentityService:
    """Olympus ID surface: global identities, tenant links, age verification."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    # ------------------------------------------------------------------
    # Global identity (Firebase federation)
    # ------------------------------------------------------------------

    def get_or_create_from_firebase(
        self,
        *,
        firebase_uid: str,
        email: str | None = None,
        phone: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        global_preferences: dict[str, Any] | None = None,
    ) -> OlympusIdentity:
        """Get-or-create the global Olympus identity for a Firebase user.

        If an identity already exists for ``firebase_uid`` it is returned
        unchanged; the optional fields are only used when a new row has to
        be inserted. Safe to call on every sign-in — it is idempotent.
        """
        payload: dict[str, Any] = {"firebase_uid": firebase_uid}
        if email is not None:
            payload["email"] = email
        if phone is not None:
            payload["phone"] = phone
        if first_name is not None:
            payload["first_name"] = first_name
        if last_name is not None:
            payload["last_name"] = last_name
        if global_preferences is not None:
            payload["global_preferences"] = global_preferences
        data = self._http.post("/platform/identities", json=payload)
        return OlympusIdentity.from_dict(data)

    def link_to_tenant(
        self,
        *,
        olympus_id: str,
        tenant_id: str,
        commerce_customer_id: str,
    ) -> None:
        """Link a global identity to a tenant-scoped commerce customer.

        Should be called the first time a federated user transacts with a
        new tenant — typically immediately after the tenant's commerce
        service creates the per-tenant customer record. Safe to call again;
        the platform de-duplicates by ``(olympus_id, tenant_id)``.
        """
        self._http.post(
            "/platform/identities/links",
            json={
                "olympus_id": olympus_id,
                "tenant_id": tenant_id,
                "commerce_customer_id": commerce_customer_id,
            },
        )

    # ------------------------------------------------------------------
    # Age Verification (Document AI) — #3009
    # ------------------------------------------------------------------

    def scan_id(self, phone: str, image_bytes: bytes) -> dict[str, Any]:
        """Scan an ID document for age verification via Google Document AI.

        The image is processed and immediately deleted — only the DOB hash
        and computed age are stored.
        """
        encoded = base64.b64encode(bytes(image_bytes)).decode("ascii")
        return self._http.post(
            "/identity/scan-id",
            json={"phone": phone, "image": encoded},
        )

    def check_verification_status(self, phone: str) -> dict[str, Any]:
        """Check a caller's verification status."""
        return self._http.get(f"/identity/status/{quote(phone, safe='')}")

    def verify_passphrase(self, phone: str, passphrase: str) -> dict[str, Any]:
        """Verify a caller's passphrase (bcrypt comparison)."""
        return self._http.post(
            "/identity/verify-passphrase",
            json={"phone": phone, "passphrase": passphrase},
        )

    def set_passphrase(self, phone: str, passphrase: str) -> dict[str, Any]:
        """Set or update a caller's passphrase (bcrypt-hashed server-side)."""
        return self._http.post(
            "/identity/set-passphrase",
            json={"phone": phone, "passphrase": passphrase},
        )

    def create_upload_session(self) -> dict[str, Any]:
        """Create a signed upload URL for the caller to upload their ID photo."""
        return self._http.post("/identity/create-upload-session")

    # ------------------------------------------------------------------
    # Invites (#3403 §4.2 + §4.4)
    # ------------------------------------------------------------------

    def invite(
        self,
        *,
        email: str,
        role: str,
        location_id: str | None = None,
        message: str | None = None,
        ttl_seconds: int | None = None,
    ) -> InviteHandle:
        """Invite a user to the active tenant (manager or tenant_admin).

        The returned :class:`InviteHandle` carries ``token`` (the signed
        JWT) — surface it once to the inviter (copyable link, email body)
        and never store it client-side. The server keeps only a SHA-256
        hash for replay-block.

        ``role`` must be one of: ``tenant_admin``, ``manager``, ``staff``,
        ``employee``, ``viewer``, ``accountant``, ``developer``. ``ttl_seconds``
        defaults to 7 days and is clamped to ``[60, 30*86400]`` server-side.

        Emits ``platform.identity.invited``.
        """
        payload: dict[str, Any] = {"email": email, "role": role}
        if location_id is not None:
            payload["location_id"] = location_id
        if message is not None:
            payload["message"] = message
        if ttl_seconds is not None:
            payload["ttl_seconds"] = ttl_seconds
        data = self._http.post("/identity/invite", json=payload)
        return InviteHandle.from_dict(data)

    def list_invites(self) -> list[InviteHandle]:
        """List pending + historical invites for the active tenant."""
        data = self._http.get("/identity/invites")
        if isinstance(data, list):
            rows: list[dict[str, Any]] = data
        elif isinstance(data, dict) and isinstance(data.get("invites"), list):
            rows = data["invites"]
        else:
            rows = []
        return [InviteHandle.from_dict(r) for r in rows if isinstance(r, dict)]

    def accept_invite(self, token: str, firebase_id_token: str) -> dict[str, Any]:
        """Accept an invite token using a Firebase ID-token proof.

        The platform verifies the invite-JWT signature + expiry, matches
        the caller's Firebase email against the invite's email, delegates
        to the Firebase-exchange pipeline (which creates the ``auth_users``
        row if missing), then layers the invited role + location on top.

        Returns the same ``VerifyFirebaseTokenResponse`` envelope the
        Firebase-exchange endpoint emits (``{user, access_token,
        refresh_token, tenant_id, ...}``). Apps can hand this directly to
        :meth:`OlympusClient.set_access_token`.

        Emits ``platform.identity.invite_accepted``.
        """
        token_path = quote(token, safe="")
        return self._http.post(
            f"/identity/invites/{token_path}/accept",
            json={"firebase_id_token": firebase_id_token},
        )

    def revoke_invite(self, invite_id: str) -> None:
        """Revoke a pending invite (idempotent — revoking twice is a no-op).

        Requires manager or tenant_admin role.
        """
        invite_path = quote(invite_id, safe="")
        self._http.post(f"/identity/invites/{invite_path}/revoke")

    def remove_from_tenant(
        self,
        *,
        user_id: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Remove a user from the active tenant without deleting their
        Firebase identity.

        Requires tenant_admin. Revokes the user's tenant-scoped role
        assignments and invalidates their active sessions. The user's
        global Olympus identity (Firebase UID, email, phone) is preserved
        — they can still sign in to other tenants where they have rows.

        Emits ``platform.identity.removed_from_tenant``.
        """
        payload: dict[str, Any] = {"user_id": user_id}
        if reason is not None:
            payload["reason"] = reason
        return self._http.post("/identity/remove_from_tenant", json=payload)
