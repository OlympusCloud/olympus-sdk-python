"""Smart home integration: platforms, devices, rooms, scenes, automations.

Routes: ``/smart-home/*``.

Wraps the Go API Gateway smart-home surface that aggregates connected
platforms (Hue, SmartThings, HomeKit, Matter, etc.) into a single tenant
view for Maximus and consumer-app shells.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import quote

if TYPE_CHECKING:
    from olympus_sdk.http import OlympusHttpClient


def _list_from(
    body: dict[str, Any] | None,
    *,
    primary_key: str,
) -> list[dict[str, Any]]:
    """Extract a list of rows from a response that uses either
    ``{<primary_key>: [...]}`` or ``{data: [...]}``.

    Mirrors the dart fallback chain so SDKs stay compatible when routes are
    wrapped in a generic envelope.
    """
    if not isinstance(body, dict):
        return []
    value = body.get(primary_key)
    if not isinstance(value, list):
        value = body.get("data")
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


class SmartHomeService:
    """Smart-home: platforms, devices, rooms, scenes, automations."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    # ------------------------------------------------------------------
    # Platforms + devices
    # ------------------------------------------------------------------

    def list_platforms(self) -> list[dict[str, Any]]:
        """List connected smart-home platforms (e.g., Hue, SmartThings)."""
        return _list_from(self._http.get("/smart-home/platforms"), primary_key="platforms")

    def list_devices(
        self,
        *,
        platform_id: str | None = None,
        room_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """List all smart-home devices across connected platforms."""
        body = self._http.get(
            "/smart-home/devices",
            params={"platform_id": platform_id, "room_id": room_id},
        )
        return _list_from(body, primary_key="devices")

    def get_device(self, device_id: str) -> dict[str, Any]:
        """Get details for a single smart-home device."""
        return self._http.get(f"/smart-home/devices/{quote(device_id, safe='')}")

    def control_device(
        self,
        device_id: str,
        command: dict[str, Any],
    ) -> dict[str, Any]:
        """Send a control command to a device (on/off, brightness, color, etc.)."""
        return self._http.post(
            f"/smart-home/devices/{quote(device_id, safe='')}/control",
            json=command,
        )

    def list_rooms(self) -> list[dict[str, Any]]:
        """List rooms with their associated devices."""
        return _list_from(self._http.get("/smart-home/rooms"), primary_key="rooms")

    # ------------------------------------------------------------------
    # Scenes (Issue #2569)
    # ------------------------------------------------------------------

    def list_scenes(self) -> list[dict[str, Any]]:
        """List automation scenes (e.g., "Good morning", "Movie night")."""
        return _list_from(self._http.get("/smart-home/scenes"), primary_key="scenes")

    def activate_scene(self, scene_id: str) -> dict[str, Any]:
        """Activate a scene by ID."""
        return self._http.post(f"/smart-home/scenes/{quote(scene_id, safe='')}/activate")

    def create_scene(self, scene: dict[str, Any]) -> dict[str, Any]:
        """Create a new scene with devices and actions."""
        return self._http.post("/smart-home/scenes", json=scene)

    def delete_scene(self, scene_id: str) -> None:
        """Delete a scene."""
        self._http.delete(f"/smart-home/scenes/{quote(scene_id, safe='')}")

    # ------------------------------------------------------------------
    # Automations
    # ------------------------------------------------------------------

    def list_automations(self) -> list[dict[str, Any]]:
        """List automation rules (trigger-action)."""
        return _list_from(self._http.get("/smart-home/automations"), primary_key="automations")

    def create_automation(self, automation: dict[str, Any]) -> dict[str, Any]:
        """Create a new automation rule."""
        return self._http.post("/smart-home/automations", json=automation)

    def delete_automation(self, automation_id: str) -> None:
        """Delete an automation rule."""
        self._http.delete(f"/smart-home/automations/{quote(automation_id, safe='')}")
