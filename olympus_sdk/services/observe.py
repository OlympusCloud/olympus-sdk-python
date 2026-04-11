"""Client-side observability: event logging, error reporting, tracing, and user identification.

Routes: ``/monitoring/client/*``, ``/analytics/*``.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from olympus_sdk.models.observe import TraceHandle

if TYPE_CHECKING:
    from olympus_sdk.http import OlympusHttpClient


class ObserveService:
    """Client-side observability: event logging, error reporting, tracing, and user identification."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    def log_event(self, name: str, properties: dict[str, Any]) -> None:
        """Log a custom analytics event."""
        self._http.post("/monitoring/client/events", json={
            "event": name,
            "properties": properties,
            "timestamp": datetime.now().isoformat(),
        })

    def log_error(
        self,
        error: str,
        *,
        stack_trace: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Report a client-side error."""
        payload: dict[str, Any] = {
            "error": error,
            "timestamp": datetime.now().isoformat(),
        }
        if stack_trace is not None:
            payload["stack_trace"] = stack_trace
        if context is not None:
            payload["context"] = context
        self._http.post("/monitoring/client/errors", json=payload)

    def start_trace(self, name: str) -> TraceHandle:
        """Start a client-side trace span.

        Call ``handle.end()`` to close the span and report its duration.
        """
        now = datetime.now()
        trace_id = f"{int(now.timestamp() * 1000)}-{abs(hash(name))}"

        def _on_end(handle: TraceHandle, duration_ms: float) -> None:
            self._http.post("/monitoring/client/traces", json={
                "trace_id": handle.trace_id,
                "name": handle.name,
                "duration_ms": int(duration_ms),
                "started_at": handle.started_at.isoformat(),
                "ended_at": handle.ended_at.isoformat() if handle.ended_at else None,
            })

        return TraceHandle(
            name=name,
            trace_id=trace_id,
            started_at=now,
            on_end=_on_end,
        )

    def set_user(self, user_id: str, *, properties: dict[str, Any] | None = None) -> None:
        """Identify the current user for analytics attribution."""
        payload: dict[str, Any] = {"user_id": user_id}
        if properties is not None:
            payload["properties"] = properties
        self._http.post("/monitoring/client/identify", json=payload)
