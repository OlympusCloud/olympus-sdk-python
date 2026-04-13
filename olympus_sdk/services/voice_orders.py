"""Voice order placement (#2999).

Wraps the Olympus voice order service via the Go API Gateway.
AI voice agents collect orders by phone, validate prices against the
menu, store orders in the database, and push them to POS systems.
Routes: ``/voice-orders/*``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from olympus_sdk.http import OlympusHttpClient


class VoiceOrdersService:
    """Voice orders: create, track, and push phone orders to POS."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a voice order with price validation.

        ``data`` must include ``location_id`` and ``items`` (list of dicts
        with ``menu_item_id``, ``name``, ``quantity``, ``unit_price``).
        Optional fields: ``fulfillment`` (pickup/delivery),
        ``delivery_address``, ``payment_method``, ``caller_phone``,
        ``caller_name``, ``call_sid``, ``agent_id``, ``metadata``.

        Item prices are validated against the menu catalog. If an AI-provided
        price deviates more than 10% from the menu price, the menu price is
        used instead (hallucination guard).
        """
        return self._http.post("/voice-orders", json=data)

    def get(self, order_id: str) -> dict[str, Any]:
        """Get a voice order by ID."""
        return self._http.get(f"/voice-orders/{order_id}")

    def list(
        self,
        *,
        caller_phone: str | None = None,
        status: str | None = None,
        location_id: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """List voice orders with optional filters.

        Args:
            caller_phone: Filter by caller phone number.
            status: Filter by order status (e.g. ``pending``, ``confirmed``).
            location_id: Filter by location.
            limit: Maximum number of results (1-100, default 20).
        """
        return self._http.get(
            "/voice-orders",
            params={
                "caller_phone": caller_phone,
                "status": status,
                "location_id": location_id,
                "limit": limit,
            },
        )

    def push_to_pos(self, order_id: str) -> dict[str, Any]:
        """Push a voice order to the tenant's POS system.

        Submits the order to the configured POS integration
        (Toast, Square, Clover) and updates the push status.
        """
        return self._http.post(f"/voice-orders/{order_id}/push-pos")
