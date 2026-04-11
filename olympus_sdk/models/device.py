"""Device management models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class Device:
    """A managed device enrolled via MDM."""

    id: str
    name: str | None = None
    status: str | None = None
    profile: str | None = None
    platform: str | None = None
    os_version: str | None = None
    app_version: str | None = None
    location_id: str | None = None
    last_seen: datetime | None = None
    enrolled_at: datetime | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Device:
        return Device(
            id=data.get("id") or data.get("device_id", ""),
            name=data.get("name"),
            status=data.get("status"),
            profile=data.get("profile"),
            platform=data.get("platform"),
            os_version=data.get("os_version"),
            app_version=data.get("app_version"),
            location_id=data.get("location_id"),
            last_seen=datetime.fromisoformat(data["last_seen"]) if data.get("last_seen") else None,
            enrolled_at=datetime.fromisoformat(data["enrolled_at"]) if data.get("enrolled_at") else None,
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"id": self.id}
        if self.name is not None:
            result["name"] = self.name
        if self.status is not None:
            result["status"] = self.status
        if self.profile is not None:
            result["profile"] = self.profile
        if self.platform is not None:
            result["platform"] = self.platform
        if self.os_version is not None:
            result["os_version"] = self.os_version
        if self.app_version is not None:
            result["app_version"] = self.app_version
        if self.location_id is not None:
            result["location_id"] = self.location_id
        if self.last_seen is not None:
            result["last_seen"] = self.last_seen.isoformat()
        if self.enrolled_at is not None:
            result["enrolled_at"] = self.enrolled_at.isoformat()
        return result

    @property
    def is_online(self) -> bool:
        if self.last_seen is None:
            return False
        now = datetime.now(tz=self.last_seen.tzinfo or timezone.utc)
        return (now - self.last_seen).total_seconds() < 300
