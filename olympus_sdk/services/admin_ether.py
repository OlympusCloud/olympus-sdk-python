"""Admin API for managing the Ether AI model catalog at runtime.

Provides CRUD for models and tiers, plus hot-reload of the catalog cache.
Routes: ``/admin/ether/*``.

Requires: admin role (super_admin, platform_admin).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from olympus_sdk.http import OlympusHttpClient


class AdminEtherService:
    """Admin API for managing the Ether AI model catalog at runtime."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    # ------------------------------------------------------------------
    # Model CRUD
    # ------------------------------------------------------------------

    def create_model(self, model: dict[str, Any]) -> dict[str, Any]:
        """Register a new AI model in the Ether catalog."""
        return self._http.post("/admin/ether/models", json=model)

    def update_model(
        self, model_id: str, updates: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an existing model's configuration."""
        return self._http.put(f"/admin/ether/models/{model_id}", json=updates)

    def delete_model(self, model_id: str) -> None:
        """Remove a model from the catalog."""
        self._http.delete(f"/admin/ether/models/{model_id}")

    def list_models(
        self,
        *,
        tier: str | None = None,
        provider: str | None = None,
    ) -> list[dict[str, Any]]:
        """List models in the catalog, optionally filtered by tier or provider."""
        data = self._http.get(
            "/admin/ether/models",
            params={"tier": tier, "provider": provider},
        )
        return data.get("models") or data.get("data") or []

    # ------------------------------------------------------------------
    # Tier Management
    # ------------------------------------------------------------------

    def list_tiers(self) -> list[dict[str, Any]]:
        """List all Ether tiers (T1-T6) with current configuration."""
        data = self._http.get("/admin/ether/tiers")
        return data.get("tiers") or data.get("data") or []

    def update_tier(
        self, tier_number: int, updates: dict[str, Any]
    ) -> dict[str, Any]:
        """Update a tier's configuration (e.g. default model, rate limits)."""
        return self._http.put(
            f"/admin/ether/tiers/{tier_number}", json=updates
        )

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------

    def reload_catalog(self) -> None:
        """Force a hot-reload of the model catalog from the backing store."""
        self._http.post("/admin/ether/catalog/reload")
