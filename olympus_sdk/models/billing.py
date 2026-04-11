"""Billing models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Plan:
    """A billing plan (Ember, Spark, Blaze, Inferno, Olympus)."""

    id: str
    name: str
    tier: str | None = None
    monthly_price: int | None = None
    annual_price: int | None = None
    max_locations: int | None = None
    max_agents: int | None = None
    ai_credits: int | None = None
    voice_minutes: int | None = None
    features: list[str] = field(default_factory=list)
    status: str | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Plan:
        features_raw = data.get("features")
        return Plan(
            id=data.get("id") or data.get("plan_id", ""),
            name=data.get("name", ""),
            tier=data.get("tier"),
            monthly_price=data.get("monthly_price"),
            annual_price=data.get("annual_price"),
            max_locations=data.get("max_locations"),
            max_agents=data.get("max_agents"),
            ai_credits=data.get("ai_credits"),
            voice_minutes=data.get("voice_minutes"),
            features=list(features_raw) if features_raw else [],
            status=data.get("status"),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"id": self.id, "name": self.name}
        if self.tier is not None:
            result["tier"] = self.tier
        if self.monthly_price is not None:
            result["monthly_price"] = self.monthly_price
        if self.annual_price is not None:
            result["annual_price"] = self.annual_price
        if self.max_locations is not None:
            result["max_locations"] = self.max_locations
        if self.max_agents is not None:
            result["max_agents"] = self.max_agents
        if self.ai_credits is not None:
            result["ai_credits"] = self.ai_credits
        if self.voice_minutes is not None:
            result["voice_minutes"] = self.voice_minutes
        if self.features:
            result["features"] = self.features
        if self.status is not None:
            result["status"] = self.status
        return result


@dataclass
class InvoiceLineItem:
    """A single line item on an invoice."""

    description: str
    amount: int | None = None
    quantity: int | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> InvoiceLineItem:
        return InvoiceLineItem(
            description=data.get("description", ""),
            amount=data.get("amount"),
            quantity=data.get("quantity"),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"description": self.description}
        if self.amount is not None:
            result["amount"] = self.amount
        if self.quantity is not None:
            result["quantity"] = self.quantity
        return result


@dataclass
class UsageReport:
    """Tenant resource usage for a billing period."""

    period: str | None = None
    ai_credits_used: int | None = None
    ai_credits_limit: int | None = None
    voice_minutes_used: int | None = None
    voice_minutes_limit: int | None = None
    storage_used_mb: int | None = None
    storage_limit_mb: int | None = None
    api_calls_count: int | None = None
    location_count: int | None = None
    agent_count: int | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> UsageReport:
        return UsageReport(
            period=data.get("period"),
            ai_credits_used=data.get("ai_credits_used"),
            ai_credits_limit=data.get("ai_credits_limit"),
            voice_minutes_used=data.get("voice_minutes_used"),
            voice_minutes_limit=data.get("voice_minutes_limit"),
            storage_used_mb=data.get("storage_used_mb"),
            storage_limit_mb=data.get("storage_limit_mb"),
            api_calls_count=data.get("api_calls_count"),
            location_count=data.get("location_count"),
            agent_count=data.get("agent_count"),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if self.period is not None:
            result["period"] = self.period
        if self.ai_credits_used is not None:
            result["ai_credits_used"] = self.ai_credits_used
        if self.ai_credits_limit is not None:
            result["ai_credits_limit"] = self.ai_credits_limit
        if self.voice_minutes_used is not None:
            result["voice_minutes_used"] = self.voice_minutes_used
        if self.voice_minutes_limit is not None:
            result["voice_minutes_limit"] = self.voice_minutes_limit
        if self.storage_used_mb is not None:
            result["storage_used_mb"] = self.storage_used_mb
        if self.storage_limit_mb is not None:
            result["storage_limit_mb"] = self.storage_limit_mb
        if self.api_calls_count is not None:
            result["api_calls_count"] = self.api_calls_count
        if self.location_count is not None:
            result["location_count"] = self.location_count
        if self.agent_count is not None:
            result["agent_count"] = self.agent_count
        return result

    @property
    def ai_credits_percentage(self) -> float:
        if self.ai_credits_limit and self.ai_credits_limit > 0:
            return (self.ai_credits_used or 0) / self.ai_credits_limit
        return 0.0

    @property
    def voice_minutes_percentage(self) -> float:
        if self.voice_minutes_limit and self.voice_minutes_limit > 0:
            return (self.voice_minutes_used or 0) / self.voice_minutes_limit
        return 0.0


@dataclass
class Invoice:
    """A billing invoice."""

    id: str
    status: str | None = None
    amount: int | None = None
    currency: str | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    paid_at: datetime | None = None
    pdf_url: str | None = None
    line_items: list[InvoiceLineItem] = field(default_factory=list)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Invoice:
        items_raw = data.get("line_items") or []
        return Invoice(
            id=data.get("id") or data.get("invoice_id", ""),
            status=data.get("status"),
            amount=data.get("amount"),
            currency=data.get("currency"),
            period_start=datetime.fromisoformat(data["period_start"]) if data.get("period_start") else None,
            period_end=datetime.fromisoformat(data["period_end"]) if data.get("period_end") else None,
            paid_at=datetime.fromisoformat(data["paid_at"]) if data.get("paid_at") else None,
            pdf_url=data.get("pdf_url"),
            line_items=[InvoiceLineItem.from_dict(i) for i in items_raw],
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"id": self.id}
        if self.status is not None:
            result["status"] = self.status
        if self.amount is not None:
            result["amount"] = self.amount
        if self.currency is not None:
            result["currency"] = self.currency
        if self.period_start is not None:
            result["period_start"] = self.period_start.isoformat()
        if self.period_end is not None:
            result["period_end"] = self.period_end.isoformat()
        if self.paid_at is not None:
            result["paid_at"] = self.paid_at.isoformat()
        if self.pdf_url is not None:
            result["pdf_url"] = self.pdf_url
        if self.line_items:
            result["line_items"] = [i.to_dict() for i in self.line_items]
        return result
