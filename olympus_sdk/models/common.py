"""Shared types used across all Olympus SDK services."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

T = TypeVar("T")


@dataclass
class Pagination:
    """Pagination metadata returned by list endpoints."""

    page: int = 1
    per_page: int = 20
    total: int = 0
    total_pages: int = 0

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Pagination:
        return Pagination(
            page=data.get("page", 1),
            per_page=data.get("per_page", 20),
            total=data.get("total", 0),
            total_pages=data.get("total_pages", 0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "page": self.page,
            "per_page": self.per_page,
            "total": self.total,
            "total_pages": self.total_pages,
        }

    @property
    def has_next_page(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_previous_page(self) -> bool:
        return self.page > 1


@dataclass
class PaginatedResponse:
    """Paginated response wrapper for list endpoints."""

    data: list[Any]
    pagination: Pagination

    @staticmethod
    def from_dict(
        raw: dict[str, Any],
        item_parser: Callable[[dict[str, Any]], Any],
    ) -> PaginatedResponse:
        items_raw = raw.get("data") or []
        items = [item_parser(i) for i in items_raw]
        pagination_raw = raw.get("pagination")
        if pagination_raw:
            pagination = Pagination.from_dict(pagination_raw)
        else:
            pagination = Pagination(
                page=raw.get("page", 1),
                per_page=raw.get("per_page", len(items)),
                total=raw.get("total", len(items)),
                total_pages=raw.get("total_pages", 1),
            )
        return PaginatedResponse(data=items, pagination=pagination)


@dataclass
class WebhookRegistration:
    """Webhook registration returned by the events service."""

    id: str
    url: str
    events: list[str] = field(default_factory=list)
    secret: str | None = None
    created_at: datetime | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> WebhookRegistration:
        events_raw = data.get("events") or []
        return WebhookRegistration(
            id=data["id"],
            url=data["url"],
            events=list(events_raw),
            secret=data.get("secret"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"id": self.id, "url": self.url, "events": self.events}
        if self.secret is not None:
            result["secret"] = self.secret
        if self.created_at is not None:
            result["created_at"] = self.created_at.isoformat()
        return result


@dataclass
class SearchResult:
    """Generic search result returned by data and AI search operations."""

    id: str
    score: float = 0.0
    content: str | None = None
    metadata: dict[str, Any] | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> SearchResult:
        return SearchResult(
            id=data["id"],
            score=float(data.get("score", 0.0)),
            content=data.get("content"),
            metadata=data.get("metadata"),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"id": self.id, "score": self.score}
        if self.content is not None:
            result["content"] = self.content
        if self.metadata is not None:
            result["metadata"] = self.metadata
        return result


@dataclass
class PolicyResult:
    """Policy evaluation result returned by the gating service."""

    allowed: bool = False
    value: Any = None
    reason: str | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> PolicyResult:
        return PolicyResult(
            allowed=data.get("allowed", False),
            value=data.get("value"),
            reason=data.get("reason"),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"allowed": self.allowed}
        if self.value is not None:
            result["value"] = self.value
        if self.reason is not None:
            result["reason"] = self.reason
        return result
