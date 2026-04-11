"""Payment models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class Payment:
    """A completed or pending payment."""

    id: str
    status: str = "pending"
    order_id: str | None = None
    amount: int | None = None
    currency: str | None = None
    method: str | None = None
    stripe_payment_intent_id: str | None = None
    created_at: datetime | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Payment:
        return Payment(
            id=data.get("id") or data.get("payment_id", ""),
            status=data.get("status", "pending"),
            order_id=data.get("order_id"),
            amount=data.get("amount"),
            currency=data.get("currency"),
            method=data.get("method") or data.get("payment_method"),
            stripe_payment_intent_id=data.get("stripe_payment_intent_id"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"id": self.id, "status": self.status}
        if self.order_id is not None:
            result["order_id"] = self.order_id
        if self.amount is not None:
            result["amount"] = self.amount
        if self.currency is not None:
            result["currency"] = self.currency
        if self.method is not None:
            result["method"] = self.method
        if self.stripe_payment_intent_id is not None:
            result["stripe_payment_intent_id"] = self.stripe_payment_intent_id
        if self.created_at is not None:
            result["created_at"] = self.created_at.isoformat()
        return result


@dataclass
class Refund:
    """A refund issued against a payment."""

    id: str
    payment_id: str
    status: str = "pending"
    amount: int | None = None
    reason: str | None = None
    created_at: datetime | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Refund:
        return Refund(
            id=data.get("id") or data.get("refund_id", ""),
            payment_id=data.get("payment_id", ""),
            status=data.get("status", "pending"),
            amount=data.get("amount"),
            reason=data.get("reason"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "payment_id": self.payment_id,
            "status": self.status,
        }
        if self.amount is not None:
            result["amount"] = self.amount
        if self.reason is not None:
            result["reason"] = self.reason
        if self.created_at is not None:
            result["created_at"] = self.created_at.isoformat()
        return result


@dataclass
class Balance:
    """Account balance information."""

    available: int = 0
    pending: int = 0
    currency: str | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Balance:
        return Balance(
            available=data.get("available", 0),
            pending=data.get("pending", 0),
            currency=data.get("currency"),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"available": self.available, "pending": self.pending}
        if self.currency is not None:
            result["currency"] = self.currency
        return result

    @property
    def total(self) -> int:
        return self.available + self.pending


@dataclass
class Payout:
    """A payout to an external bank account or destination."""

    id: str
    status: str = "pending"
    amount: int | None = None
    currency: str | None = None
    destination: str | None = None
    method: str | None = None
    arrival_date: datetime | None = None
    created_at: datetime | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Payout:
        return Payout(
            id=data.get("id") or data.get("payout_id", ""),
            status=data.get("status", "pending"),
            amount=data.get("amount"),
            currency=data.get("currency"),
            destination=data.get("destination"),
            method=data.get("method"),
            arrival_date=datetime.fromisoformat(data["arrival_date"]) if data.get("arrival_date") else None,
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"id": self.id, "status": self.status}
        if self.amount is not None:
            result["amount"] = self.amount
        if self.currency is not None:
            result["currency"] = self.currency
        if self.destination is not None:
            result["destination"] = self.destination
        if self.method is not None:
            result["method"] = self.method
        if self.arrival_date is not None:
            result["arrival_date"] = self.arrival_date.isoformat()
        if self.created_at is not None:
            result["created_at"] = self.created_at.isoformat()
        return result


@dataclass
class TerminalReader:
    """A physical card reader registered via Stripe Terminal."""

    id: str
    device_type: str | None = None
    label: str | None = None
    location_id: str | None = None
    serial_number: str | None = None
    status: str | None = None
    ip_address: str | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> TerminalReader:
        return TerminalReader(
            id=data.get("id", ""),
            device_type=data.get("device_type"),
            label=data.get("label"),
            location_id=data.get("location") or data.get("location_id"),
            serial_number=data.get("serial_number"),
            status=data.get("status"),
            ip_address=data.get("ip_address"),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"id": self.id}
        if self.device_type is not None:
            result["device_type"] = self.device_type
        if self.label is not None:
            result["label"] = self.label
        if self.location_id is not None:
            result["location"] = self.location_id
        if self.serial_number is not None:
            result["serial_number"] = self.serial_number
        if self.status is not None:
            result["status"] = self.status
        if self.ip_address is not None:
            result["ip_address"] = self.ip_address
        return result


@dataclass
class TerminalPayment:
    """The result of presenting a payment to a terminal reader."""

    id: str
    status: str = "pending"
    amount: int | None = None
    currency: str | None = None
    reader_id: str | None = None
    payment_intent_id: str | None = None
    created_at: datetime | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> TerminalPayment:
        return TerminalPayment(
            id=data.get("id", ""),
            status=data.get("status", "pending"),
            amount=data.get("amount"),
            currency=data.get("currency"),
            reader_id=data.get("reader_id"),
            payment_intent_id=data.get("payment_intent_id") or data.get("payment_intent"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"id": self.id, "status": self.status}
        if self.amount is not None:
            result["amount"] = self.amount
        if self.currency is not None:
            result["currency"] = self.currency
        if self.reader_id is not None:
            result["reader_id"] = self.reader_id
        if self.payment_intent_id is not None:
            result["payment_intent_id"] = self.payment_intent_id
        if self.created_at is not None:
            result["created_at"] = self.created_at.isoformat()
        return result
