"""Commerce models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class OrderModifier:
    """A modifier applied to an order item."""

    id: str
    name: str
    price: int | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> OrderModifier:
        return OrderModifier(
            id=data["id"],
            name=data["name"],
            price=data.get("price"),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"id": self.id, "name": self.name}
        if self.price is not None:
            result["price"] = self.price
        return result


@dataclass
class OrderItem:
    """A single line item within an order."""

    catalog_id: str
    qty: int
    price: int
    id: str | None = None
    name: str | None = None
    modifiers: list[OrderModifier] = field(default_factory=list)
    notes: str | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> OrderItem:
        mods_raw = data.get("modifiers") or []
        return OrderItem(
            catalog_id=data.get("catalog_id") or data.get("menu_item_id", ""),
            qty=data.get("qty") or data.get("quantity", 1),
            price=data.get("price", 0),
            id=data.get("id"),
            name=data.get("name"),
            modifiers=[OrderModifier.from_dict(m) for m in mods_raw],
            notes=data.get("notes"),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "catalog_id": self.catalog_id,
            "qty": self.qty,
            "price": self.price,
        }
        if self.id is not None:
            result["id"] = self.id
        if self.name is not None:
            result["name"] = self.name
        if self.modifiers:
            result["modifiers"] = [m.to_dict() for m in self.modifiers]
        if self.notes is not None:
            result["notes"] = self.notes
        return result


@dataclass
class Order:
    """An order in the commerce system."""

    id: str
    status: str = "pending"
    items: list[OrderItem] = field(default_factory=list)
    source: str | None = None
    table_id: str | None = None
    customer_id: str | None = None
    subtotal: int | None = None
    tax: int | None = None
    total: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Order:
        items_raw = data.get("items") or []
        return Order(
            id=data["id"],
            status=data.get("status", "pending"),
            items=[OrderItem.from_dict(i) for i in items_raw],
            source=data.get("source"),
            table_id=data.get("table_id"),
            customer_id=data.get("customer_id"),
            subtotal=data.get("subtotal"),
            tax=data.get("tax"),
            total=data.get("total"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None,
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"id": self.id, "status": self.status}
        if self.items:
            result["items"] = [i.to_dict() for i in self.items]
        if self.source is not None:
            result["source"] = self.source
        if self.table_id is not None:
            result["table_id"] = self.table_id
        if self.customer_id is not None:
            result["customer_id"] = self.customer_id
        if self.subtotal is not None:
            result["subtotal"] = self.subtotal
        if self.tax is not None:
            result["tax"] = self.tax
        if self.total is not None:
            result["total"] = self.total
        if self.created_at is not None:
            result["created_at"] = self.created_at.isoformat()
        if self.updated_at is not None:
            result["updated_at"] = self.updated_at.isoformat()
        return result


@dataclass
class CatalogModifierOption:
    """An individual option within a catalog modifier group."""

    id: str
    name: str
    price: int | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> CatalogModifierOption:
        return CatalogModifierOption(
            id=data["id"],
            name=data["name"],
            price=data.get("price"),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"id": self.id, "name": self.name}
        if self.price is not None:
            result["price"] = self.price
        return result


@dataclass
class CatalogModifier:
    """A modifier definition within a catalog item."""

    id: str
    name: str
    price: int | None = None
    required: bool | None = None
    options: list[CatalogModifierOption] = field(default_factory=list)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> CatalogModifier:
        opts_raw = data.get("options") or []
        return CatalogModifier(
            id=data["id"],
            name=data["name"],
            price=data.get("price"),
            required=data.get("required"),
            options=[CatalogModifierOption.from_dict(o) for o in opts_raw],
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"id": self.id, "name": self.name}
        if self.price is not None:
            result["price"] = self.price
        if self.required is not None:
            result["required"] = self.required
        if self.options:
            result["options"] = [o.to_dict() for o in self.options]
        return result


@dataclass
class CatalogItem:
    """A catalog item (menu item, product, etc.)."""

    id: str
    name: str
    price: int = 0
    description: str | None = None
    category: str | None = None
    category_id: str | None = None
    image_url: str | None = None
    modifiers: list[CatalogModifier] = field(default_factory=list)
    available: bool | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> CatalogItem:
        mods_raw = data.get("modifiers") or []
        return CatalogItem(
            id=data["id"],
            name=data["name"],
            price=data.get("price", 0),
            description=data.get("description"),
            category=data.get("category"),
            category_id=data.get("category_id"),
            image_url=data.get("image_url"),
            modifiers=[CatalogModifier.from_dict(m) for m in mods_raw],
            available=data.get("available"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None,
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"id": self.id, "name": self.name, "price": self.price}
        if self.description is not None:
            result["description"] = self.description
        if self.category is not None:
            result["category"] = self.category
        if self.category_id is not None:
            result["category_id"] = self.category_id
        if self.image_url is not None:
            result["image_url"] = self.image_url
        if self.modifiers:
            result["modifiers"] = [m.to_dict() for m in self.modifiers]
        if self.available is not None:
            result["available"] = self.available
        if self.created_at is not None:
            result["created_at"] = self.created_at.isoformat()
        if self.updated_at is not None:
            result["updated_at"] = self.updated_at.isoformat()
        return result
