"""Olympus Marketplace: discover, install, and manage third-party apps.

Routes: ``/marketplace/*`` (Algolia-powered discovery + Spanner install state).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from olympus_sdk.models.marketplace import Installation, MarketplaceApp

if TYPE_CHECKING:
    from olympus_sdk.http import OlympusHttpClient


class MarketplaceService:
    """Marketplace: discover, install, and manage third-party apps."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    def list_apps(
        self,
        *,
        category: str | None = None,
        industry: str | None = None,
        query: str | None = None,
        limit: int | None = None,
    ) -> list[MarketplaceApp]:
        """List available marketplace apps with optional filters."""
        data = self._http.get("/marketplace/apps", params={
            "category": category,
            "industry": industry,
            "q": query,
            "limit": limit,
        })
        items_raw = data.get("apps") or data.get("data") or []
        return [MarketplaceApp.from_dict(a) for a in items_raw]

    def get_app(self, app_id: str) -> MarketplaceApp:
        """Get details for a single marketplace app."""
        data = self._http.get(f"/marketplace/apps/{app_id}")
        return MarketplaceApp.from_dict(data)

    def install(self, app_id: str) -> Installation:
        """Install a marketplace app for the current tenant."""
        data = self._http.post(f"/marketplace/apps/{app_id}/install")
        return Installation.from_dict(data)

    def uninstall(self, app_id: str) -> None:
        """Uninstall a marketplace app."""
        self._http.post(f"/marketplace/apps/{app_id}/uninstall")

    def get_installed(self) -> list[Installation]:
        """List apps currently installed for the tenant."""
        data = self._http.get("/marketplace/installed")
        items_raw = data.get("installations") or data.get("data") or []
        return [Installation.from_dict(i) for i in items_raw]

    def review(self, app_id: str, rating: int, text: str) -> None:
        """Submit a review for a marketplace app."""
        self._http.post(
            f"/marketplace/apps/{app_id}/reviews",
            json={"rating": rating, "text": text},
        )
