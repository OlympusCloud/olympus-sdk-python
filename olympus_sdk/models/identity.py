"""Olympus ID (global, cross-tenant identity & federation) models.

An :class:`OlympusIdentity` is a global, cross-tenant identity representing
a single human (consumer or operator) across every Olympus Cloud app. It is
keyed by Firebase UID and may be linked to one or more tenant-scoped
commerce customers via :class:`IdentityLink`.

Source of truth: the Rust platform service Identity handler exposed via the
Go API Gateway at ``/platform/identities`` and ``/platform/identities/links``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class OlympusIdentity:
    """Global identity representing a consumer or business operator across
    all Olympus Cloud apps.

    Backed by ``platform_olympus_identities`` in Spanner; created on first
    Firebase sign-in and reused thereafter.
    """

    #: Server-assigned global identity UUID. Stable across tenants.
    id: str
    #: Firebase Auth UID. Unique per signed-in user.
    firebase_uid: str
    #: ISO-8601 creation timestamp.
    created_at: str
    #: ISO-8601 last-update timestamp.
    updated_at: str
    email: str | None = None
    phone: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    #: Free-form JSON for cross-app preferences (theme, locale, accessibility).
    global_preferences: dict[str, Any] | None = None
    #: Cross-tenant Stripe customer ID, used by Olympus Pay for federated
    #: checkout flows.
    stripe_customer_id: str | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> OlympusIdentity:
        return OlympusIdentity(
            id=str(data.get("id", "")),
            firebase_uid=str(data.get("firebase_uid", "")),
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
            email=data.get("email"),
            phone=data.get("phone"),
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
            global_preferences=data.get("global_preferences"),
            stripe_customer_id=data.get("stripe_customer_id"),
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "firebase_uid": self.firebase_uid,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self.email is not None:
            out["email"] = self.email
        if self.phone is not None:
            out["phone"] = self.phone
        if self.first_name is not None:
            out["first_name"] = self.first_name
        if self.last_name is not None:
            out["last_name"] = self.last_name
        if self.global_preferences is not None:
            out["global_preferences"] = self.global_preferences
        if self.stripe_customer_id is not None:
            out["stripe_customer_id"] = self.stripe_customer_id
        return out


@dataclass
class IdentityLink:
    """A binding between an :class:`OlympusIdentity` and a tenant-scoped
    commerce customer.

    One Olympus identity can have many links — one per tenant the user has
    done business with. The platform de-duplicates by ``(olympus_id,
    tenant_id)``.
    """

    olympus_id: str
    tenant_id: str
    commerce_customer_id: str
    linked_at: str

    @staticmethod
    def from_dict(data: dict[str, Any]) -> IdentityLink:
        return IdentityLink(
            olympus_id=str(data.get("olympus_id", "")),
            tenant_id=str(data.get("tenant_id", "")),
            commerce_customer_id=str(data.get("commerce_customer_id", "")),
            linked_at=str(data.get("linked_at", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "olympus_id": self.olympus_id,
            "tenant_id": self.tenant_id,
            "commerce_customer_id": self.commerce_customer_id,
            "linked_at": self.linked_at,
        }
