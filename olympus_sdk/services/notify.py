"""Push, SMS, email, Slack, and in-app notifications.

Wraps the Olympus Notification service via the Go API Gateway.
Routes: ``/notifications/*``, ``/messaging/*``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from olympus_sdk.http import OlympusHttpClient


class NotifyService:
    """Push, SMS, email, Slack, and in-app notifications."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    def push(self, user_id: str, title: str, body: str) -> None:
        """Send a push notification to a user's device(s)."""
        self._http.post("/notifications/push", json={
            "user_id": user_id,
            "title": title,
            "body": body,
        })

    def sms(self, phone: str, message: str) -> None:
        """Send an SMS message."""
        self._http.post("/messaging/sms", json={"phone": phone, "message": message})

    def email(self, to: str, subject: str, html: str) -> None:
        """Send an email."""
        self._http.post("/messaging/email", json={"to": to, "subject": subject, "html": html})

    def slack(self, channel: str, message: str) -> None:
        """Send a Slack message to a channel."""
        self._http.post("/messaging/slack", json={"channel": channel, "message": message})

    def chat(self, user_id: str, message: str) -> None:
        """Send an in-app chat message to a user."""
        self._http.post("/notifications/chat", json={"user_id": user_id, "message": message})

    def list_notifications(
        self,
        *,
        limit: int | None = None,
        unread_only: bool | None = None,
    ) -> list[dict[str, Any]]:
        """List notifications for the current user."""
        data = self._http.get(
            "/notifications",
            params={"limit": limit, "unread_only": unread_only},
        )
        return data.get("notifications") or data.get("data") or []

    def mark_read(self, notification_id: str) -> None:
        """Mark a notification as read."""
        self._http.patch(f"/notifications/{notification_id}", json={"read": True})
