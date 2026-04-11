"""Mobile Device Management (MDM): enrollment, kiosk mode, updates, and wipe.

Routes: ``/platform/device/*``, ``/diagnostics/*``, ``/auth/devices/*``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from olympus_sdk.models.device import Device

if TYPE_CHECKING:
    from olympus_sdk.http import OlympusHttpClient


class DevicesService:
    """Mobile Device Management (MDM): enrollment, kiosk mode, updates, and wipe."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    def enroll(self, device_id: str, profile: str) -> Device:
        """Enroll a device with a profile.

        ``profile`` specifies the device role (e.g. "kiosk", "pos_terminal",
        "kds", "signage").
        """
        data = self._http.post("/auth/devices/register", json={
            "device_id": device_id,
            "profile": profile,
        })
        return Device.from_dict(data)

    def set_kiosk_mode(self, device_id: str, app_id: str) -> None:
        """Set a device to kiosk mode, locking it to a specific application."""
        self._http.post(
            f"/platform/device-policies/{device_id}/kiosk",
            json={"app_id": app_id, "enabled": True},
        )

    def push_update(self, device_group_id: str, version: str) -> None:
        """Push an OTA update to a device group."""
        self._http.post("/platform/device-policies/updates", json={
            "device_group_id": device_group_id,
            "target_version": version,
        })

    def wipe(self, device_id: str) -> None:
        """Remote wipe a device (factory reset)."""
        self._http.post(f"/platform/device-policies/{device_id}/wipe")

    def list_devices(self, *, location_id: str | None = None) -> list[Device]:
        """List enrolled devices for the tenant."""
        data = self._http.get("/diagnostics/devices", params={"location_id": location_id})
        items_raw = data.get("devices") or data.get("data") or []
        return [Device.from_dict(d) for d in items_raw]

    def get_device(self, device_id: str) -> Device:
        """Get device details by ID."""
        data = self._http.get(f"/diagnostics/devices/{device_id}")
        return Device.from_dict(data)
