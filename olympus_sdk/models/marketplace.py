"""Marketplace models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class MarketplaceApp:
    """An app listed on the Olympus Marketplace."""

    id: str
    name: str
    description: str | None = None
    category: str | None = None
    industry: str | None = None
    developer: str | None = None
    icon_url: str | None = None
    rating: float | None = None
    install_count: int | None = None
    pricing: str | None = None
    created_at: datetime | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> MarketplaceApp:
        return MarketplaceApp(
            id=data["id"],
            name=data["name"],
            description=data.get("description"),
            category=data.get("category"),
            industry=data.get("industry"),
            developer=data.get("developer"),
            icon_url=data.get("icon_url"),
            rating=float(data["rating"]) if data.get("rating") is not None else None,
            install_count=data.get("install_count"),
            pricing=data.get("pricing"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"id": self.id, "name": self.name}
        if self.description is not None:
            result["description"] = self.description
        if self.category is not None:
            result["category"] = self.category
        if self.industry is not None:
            result["industry"] = self.industry
        if self.developer is not None:
            result["developer"] = self.developer
        if self.icon_url is not None:
            result["icon_url"] = self.icon_url
        if self.rating is not None:
            result["rating"] = self.rating
        if self.install_count is not None:
            result["install_count"] = self.install_count
        if self.pricing is not None:
            result["pricing"] = self.pricing
        if self.created_at is not None:
            result["created_at"] = self.created_at.isoformat()
        return result


@dataclass
class Installation:
    """An installed marketplace app instance for a tenant."""

    id: str
    app_id: str
    app_name: str | None = None
    status: str | None = None
    config: dict[str, Any] | None = None
    installed_at: datetime | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Installation:
        return Installation(
            id=data.get("id") or data.get("installation_id", ""),
            app_id=data["app_id"],
            app_name=data.get("app_name"),
            status=data.get("status"),
            config=data.get("config"),
            installed_at=datetime.fromisoformat(data["installed_at"]) if data.get("installed_at") else None,
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"id": self.id, "app_id": self.app_id}
        if self.app_name is not None:
            result["app_name"] = self.app_name
        if self.status is not None:
            result["status"] = self.status
        if self.config is not None:
            result["config"] = self.config
        if self.installed_at is not None:
            result["installed_at"] = self.installed_at.isoformat()
        return result
