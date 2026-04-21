"""SMS messaging — outbound SMS, conversation history, delivery status.

Two route families are exposed:

- ``/voice/sms/*``     — voice-platform SMS attached to a voice agent config
- ``/cpaas/messages/*`` — unified CPaaS messaging (Telnyx primary, Twilio
  fallback) for provider-abstracted delivery + status

Distinct from :class:`NotifyService.sms`, which uses the legacy
``/messaging/sms`` notification surface. New integrations should prefer the
CPaaS layer for delivery reports and the voice-platform layer for
agent-scoped conversations.
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
    if not isinstance(body, dict):
        return []
    value = body.get(primary_key)
    if not isinstance(value, list):
        value = body.get("data")
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


class SmsService:
    """Tenant-scoped SMS send + conversation retrieval + provider status."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    # ------------------------------------------------------------------
    # Voice-platform SMS (tenant-scoped, agent-attached)
    # ------------------------------------------------------------------

    def send(
        self,
        *,
        config_id: str,
        to: str,
        body: str,
    ) -> dict[str, Any]:
        """Send an outbound SMS through a voice agent config.

        ``config_id`` identifies the voice-agent config (and the phone
        number assigned to it). ``to`` is the E.164 destination. ``body``
        is the message text.
        """
        return self._http.post(
            "/voice/sms/send",
            json={"config_id": config_id, "to": to, "body": body},
        )

    def get_conversations(
        self,
        phone: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[dict[str, Any]]:
        """List threaded SMS conversations for a phone number."""
        body = self._http.get(
            f"/voice/sms/conversations/{quote(phone, safe='')}",
            params={"limit": limit, "offset": offset},
        )
        return _list_from(body, primary_key="conversations")

    # ------------------------------------------------------------------
    # CPaaS Messaging (provider-abstracted, Telnyx primary / Twilio fallback)
    # ------------------------------------------------------------------

    def send_via_cpaas(
        self,
        *,
        from_: str,
        to: str,
        body: str,
        webhook_url: str | None = None,
    ) -> dict[str, Any]:
        """Send an SMS via the unified CPaaS layer.

        ``from_`` and ``to`` are E.164 phone numbers. The ``from_`` argument
        uses a trailing underscore to avoid shadowing Python's ``from``
        keyword; it is sent on the wire as the ``from`` field.

        Returns the message resource with the provider-assigned ID and
        delivery status.
        """
        payload: dict[str, Any] = {"from": from_, "to": to, "body": body}
        if webhook_url is not None:
            payload["webhook_url"] = webhook_url
        return self._http.post("/cpaas/messages/sms", json=payload)

    def get_status(self, message_id: str) -> dict[str, Any]:
        """Get the delivery status and metadata of a sent message."""
        return self._http.get(f"/cpaas/messages/{quote(message_id, safe='')}")
