"""Order management, catalog operations, and commerce workflows.

Wraps the Olympus Commerce service (Rust) via the Go API Gateway.
Routes: ``/commerce/*``, ``/central-menu/*``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from olympus_sdk.models.commerce import CatalogItem, Order
from olympus_sdk.models.common import PaginatedResponse

if TYPE_CHECKING:
    from olympus_sdk.http import OlympusHttpClient


class CommerceService:
    """Order management, catalog operations, and commerce workflows."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    def create_order(
        self,
        *,
        items: list[dict[str, Any]],
        source: str,
        table_id: str | None = None,
        customer_id: str | None = None,
    ) -> Order:
        """Create a new order.

        ``items`` is a list of dicts with keys ``catalog_id``, ``qty``, and
        ``price`` (in cents). ``source`` identifies the originating channel
        (e.g. "pos", "kiosk", "online", "drive_thru").
        """
        payload: dict[str, Any] = {"items": items, "source": source}
        if table_id is not None:
            payload["table_id"] = table_id
        if customer_id is not None:
            payload["customer_id"] = customer_id
        data = self._http.post("/commerce/orders", json=payload)
        return Order.from_dict(data)

    def get_order(self, order_id: str) -> Order:
        """Retrieve a single order by ID."""
        data = self._http.get(f"/commerce/orders/{order_id}")
        return Order.from_dict(data)

    def list_orders(
        self,
        *,
        page: int | None = None,
        limit: int | None = None,
        status: str | None = None,
    ) -> PaginatedResponse:
        """List orders with optional filters and pagination."""
        data = self._http.get(
            "/commerce/orders",
            params={"page": page, "limit": limit, "status": status},
        )
        return PaginatedResponse.from_dict(data, Order.from_dict)

    def update_order_status(self, order_id: str, status: str) -> Order:
        """Update the status of an order (e.g. "preparing", "ready", "completed")."""
        data = self._http.patch(
            f"/commerce/orders/{order_id}/status",
            json={"status": status},
        )
        return Order.from_dict(data)

    def cancel_order(self, order_id: str, reason: str) -> None:
        """Cancel an order with a reason."""
        self._http.post(f"/commerce/orders/{order_id}/cancel", json={"reason": reason})

    def add_order_items(self, order_id: str, items: list[dict[str, Any]]) -> Order:
        """Add items to an existing order."""
        data = self._http.post(
            f"/commerce/orders/{order_id}/items",
            json={"items": items},
        )
        return Order.from_dict(data)

    # ------------------------------------------------------------------
    # Catalog
    # ------------------------------------------------------------------

    def create_catalog_item(
        self,
        *,
        name: str,
        price: int,
        category: str | None = None,
        modifiers: list[dict[str, Any]] | None = None,
        description: str | None = None,
        image_url: str | None = None,
    ) -> CatalogItem:
        """Create a new catalog item (menu item, product, etc.)."""
        payload: dict[str, Any] = {"name": name, "price": price}
        if category is not None:
            payload["category"] = category
        if modifiers is not None:
            payload["modifiers"] = modifiers
        if description is not None:
            payload["description"] = description
        if image_url is not None:
            payload["image_url"] = image_url
        data = self._http.post("/central-menu/items", json=payload)
        return CatalogItem.from_dict(data)

    def get_catalog(self, *, category_id: str | None = None) -> list[CatalogItem]:
        """Retrieve the catalog, optionally filtered by category."""
        data = self._http.get("/central-menu/items", params={"category_id": category_id})
        items_raw = data.get("items") or data.get("data") or []
        return [CatalogItem.from_dict(i) for i in items_raw]

    def get_catalog_item(self, item_id: str) -> CatalogItem:
        """Get a single catalog item by ID."""
        data = self._http.get(f"/central-menu/items/{item_id}")
        return CatalogItem.from_dict(data)

    def update_catalog_item(
        self,
        item_id: str,
        *,
        name: str | None = None,
        price: int | None = None,
        category: str | None = None,
        description: str | None = None,
        available: bool | None = None,
    ) -> CatalogItem:
        """Update an existing catalog item."""
        payload: dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        if price is not None:
            payload["price"] = price
        if category is not None:
            payload["category"] = category
        if description is not None:
            payload["description"] = description
        if available is not None:
            payload["available"] = available
        data = self._http.patch(f"/central-menu/items/{item_id}", json=payload)
        return CatalogItem.from_dict(data)

    def delete_catalog_item(self, item_id: str) -> None:
        """Delete a catalog item."""
        self._http.delete(f"/central-menu/items/{item_id}")
