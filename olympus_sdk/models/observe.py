"""Observability models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass
class TraceHandle:
    """Handle returned when starting a distributed trace span.

    Call :meth:`end` to close the span and record its duration.
    """

    name: str
    trace_id: str
    started_at: datetime
    on_end: Callable[[TraceHandle, float], None] | None = field(default=None, repr=False)
    _ended_at: datetime | None = field(default=None, init=False, repr=False)

    @property
    def ended_at(self) -> datetime | None:
        return self._ended_at

    @property
    def elapsed_ms(self) -> float:
        end = self._ended_at or datetime.now()
        return (end - self.started_at).total_seconds() * 1000

    def end(self) -> None:
        """End this trace span and report its duration."""
        self._ended_at = datetime.now()
        duration_ms = (self._ended_at - self.started_at).total_seconds() * 1000
        if self.on_end is not None:
            self.on_end(self, duration_ms)
