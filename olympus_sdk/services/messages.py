"""Message queue with department routing (#2997).

Wraps the Olympus message queue service via the Go API Gateway.
AI agents route messages to business departments (manager, catering,
sales, lost-and-found, reservations) when they cannot fully handle a
request. Notification dispatch via SMS + email on create.
Routes: ``/messages/*``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from olympus_sdk.http import OlympusHttpClient


class MessagesService:
    """Message queue: department-routed messages from AI agents."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    def queue(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a message in the queue and trigger notification dispatch.

        ``data`` must include at minimum ``department`` and ``message``.
        Optional fields: ``caller_phone``, ``caller_name``, ``location_id``,
        ``priority`` (urgent/high/normal/low), ``source``, ``metadata``.
        """
        return self._http.post("/messages/queue", json=data)

    def list(
        self,
        *,
        department: str | None = None,
        status: str | None = None,
        location_id: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """List messages with optional filters.

        Args:
            department: Filter by department (e.g. ``manager``, ``catering``).
            status: Filter by status: ``pending``, ``read``, ``resolved``.
            location_id: Filter by location.
            limit: Maximum number of results (1-200, default 50).
        """
        return self._http.get(
            "/messages",
            params={
                "department": department,
                "status": status,
                "location_id": location_id,
                "limit": limit,
            },
        )

    def update(self, message_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update message status or assignment.

        ``data`` may contain ``status`` (pending/read/resolved) and/or
        ``assigned_to`` (user ID).
        """
        return self._http.patch(f"/messages/{message_id}", json=data)

    def resolve(self, message_id: str) -> dict[str, Any]:
        """Convenience method to mark a message as resolved."""
        return self._http.patch(
            f"/messages/{message_id}",
            json={"status": "resolved"},
        )

    # ------------------------------------------------------------------
    # Department routing
    # ------------------------------------------------------------------

    def list_departments(self) -> list[dict[str, Any]]:
        """List configured departments with routing rules.

        Returns a list of department routing configs including
        notification channels, recipients, and escalation settings.
        """
        data = self._http.get("/messages/departments")
        if isinstance(data, list):
            return data
        return data.get("departments") or data.get("data") or []

    def configure_department(
        self,
        department: str,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Configure routing for a department.

        ``config`` may include ``notification_channels`` (list of str),
        ``recipients`` (list of dicts with contact info),
        ``escalation_after_minutes`` (int), ``is_active`` (bool),
        and ``location_id`` (str).
        """
        return self._http.put(f"/messages/departments/{department}", json=config)
