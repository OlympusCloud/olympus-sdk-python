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
