"""Point-of-sale operations: voice orders, menu sync, and order status.

Wraps the Olympus POS service via the Go API Gateway.
Routes: ``/pos/*``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from olympus_sdk.http import OlympusHttpClient


class PosService:
    """Point-of-sale operations: voice orders, menu sync, and order status."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    async def submit_voice_order(
        self,
        *,
        transcript: str,
        location_id: str | None = None,
        source: str | None = None,
    ) -> dict:
        """Submit a voice-transcribed order for processing.

        The transcript is parsed by AI to extract order items and
        create the corresponding order in the system.
        """
        payload: dict[str, Any] = {"transcript": transcript}
        if location_id is not None:
            payload["location_id"] = location_id
        if source is not None:
            payload["source"] = source
        return self._http.post("/pos/voice-order", json=payload)

    async def sync_menu(
        self,
        *,
        location_id: str | None = None,
        force: bool | None = None,
    ) -> dict:
        """Synchronize the POS menu with the central menu catalog.

        If ``force`` is True, a full sync is triggered regardless of
        whether changes have been detected.
        """
        payload: dict[str, Any] = {}
        if location_id is not None:
            payload["location_id"] = location_id
        if force is not None:
            payload["force"] = force
        return self._http.post("/pos/menu/sync", json=payload)

    async def get_order_status(self, order_id: str) -> dict:
        """Get the real-time status of a POS order."""
        return self._http.get(f"/pos/orders/{order_id}/status")
