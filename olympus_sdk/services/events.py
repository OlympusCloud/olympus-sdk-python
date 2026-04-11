"""Real-time event subscriptions, webhooks, and event publishing.

Routes: ``/events/*``, ``/platform/tenants/me/webhooks/*``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from olympus_sdk.models.common import WebhookRegistration

if TYPE_CHECKING:
    from olympus_sdk.http import OlympusHttpClient


class EventsService:
    """Real-time event subscriptions, webhooks, and event publishing."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    # ------------------------------------------------------------------
    # Event publishing
    # ------------------------------------------------------------------

    def publish(self, event_type: str, data: dict[str, Any]) -> None:
        """Publish an event to the platform event bus."""
        self._http.post("/events/publish", json={"event_type": event_type, "data": data})

    # ------------------------------------------------------------------
    # Webhooks
    # ------------------------------------------------------------------

    def webhook_register(self, url: str, events: list[str]) -> WebhookRegistration:
        """Register a webhook endpoint for one or more event types."""
        data = self._http.post(
            "/platform/tenants/me/webhooks",
            json={"url": url, "events": events},
        )
        return WebhookRegistration.from_dict(data)

    def webhook_test(self, event_type: str) -> None:
        """Send a test webhook payload for a given event type."""
        self._http.post(
            "/platform/tenants/me/webhooks/test",
            json={"event_type": event_type},
        )

    def webhook_replay(self, event_id: str) -> None:
        """Replay a previously delivered event by its ID."""
        self._http.post(
            "/platform/tenants/me/webhooks/replay",
            json={"event_id": event_id},
        )

    def list_webhooks(self) -> list[WebhookRegistration]:
        """List registered webhooks."""
        data = self._http.get("/platform/tenants/me/webhooks")
        items_raw = data.get("webhooks") or data.get("data") or []
        return [WebhookRegistration.from_dict(w) for w in items_raw]

    def webhook_delete(self, webhook_id: str) -> None:
        """Delete a registered webhook."""
        self._http.delete(f"/platform/tenants/me/webhooks/{webhook_id}")
