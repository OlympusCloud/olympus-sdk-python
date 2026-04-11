"""Maximus AI assistant: voice, calendar, inbox, plans, and subscriptions.

Wraps the Hey Maximus AI assistant via the Go API Gateway.
Routes: ``/maximus/*``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from olympus_sdk.http import OlympusHttpClient


class MaximusService:
    """Maximus AI assistant: voice queries, calendar, inbox, and subscription management."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    # ------------------------------------------------------------------
    # Voice
    # ------------------------------------------------------------------

    async def voice_query(
        self,
        *,
        transcript: str,
        context: dict[str, Any] | None = None,
    ) -> dict:
        """Send a voice transcript to Maximus for processing."""
        payload: dict[str, Any] = {"transcript": transcript}
        if context is not None:
            payload["context"] = context
        return self._http.post("/maximus/voice/query", json=payload)

    async def get_wake_word_config(self) -> dict:
        """Get the wake word configuration for the current user."""
        return self._http.get("/maximus/voice/wake-word-config")

    # ------------------------------------------------------------------
    # Calendar
    # ------------------------------------------------------------------

    async def list_calendar_events(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict:
        """List calendar events within a date range."""
        return self._http.get(
            "/maximus/calendar/events",
            params={"start_date": start_date, "end_date": end_date},
        )

    async def create_calendar_event(
        self,
        *,
        title: str,
        start_time: str,
        end_time: str,
        description: str | None = None,
        attendees: list[str] | None = None,
    ) -> dict:
        """Create a new calendar event."""
        payload: dict[str, Any] = {
            "title": title,
            "start_time": start_time,
            "end_time": end_time,
        }
        if description is not None:
            payload["description"] = description
        if attendees is not None:
            payload["attendees"] = attendees
        return self._http.post("/maximus/calendar/events", json=payload)

    # ------------------------------------------------------------------
    # Inbox
    # ------------------------------------------------------------------

    async def list_inbox(
        self,
        *,
        page: int | None = None,
        limit: int | None = None,
        unread_only: bool | None = None,
    ) -> dict:
        """List inbox messages."""
        return self._http.get(
            "/maximus/inbox",
            params={"page": page, "limit": limit, "unread_only": unread_only},
        )

    async def send_email(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        cc: list[str] | None = None,
    ) -> dict:
        """Send an email via Maximus."""
        payload: dict[str, Any] = {"to": to, "subject": subject, "body": body}
        if cc is not None:
            payload["cc"] = cc
        return self._http.post("/maximus/inbox/send", json=payload)

    # ------------------------------------------------------------------
    # Plans & Subscription
    # ------------------------------------------------------------------

    async def list_plans(self) -> dict:
        """List available Maximus subscription plans."""
        return self._http.get("/maximus/plans")

    async def get_usage(self) -> dict:
        """Get current usage metrics for the Maximus subscription."""
        return self._http.get("/maximus/usage")

    async def subscribe(
        self,
        *,
        plan_id: str,
        payment_method_id: str | None = None,
    ) -> dict:
        """Subscribe to a Maximus plan."""
        payload: dict[str, Any] = {"plan_id": plan_id}
        if payment_method_id is not None:
            payload["payment_method_id"] = payment_method_id
        return self._http.post("/maximus/subscribe", json=payload)
