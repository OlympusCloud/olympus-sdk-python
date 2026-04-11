"""Data query, CRUD, and search operations.

Provides a high-level data access layer over the Olympus platform.
Routes: ``/data/*``, ``/ai/search``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from olympus_sdk.models.common import SearchResult

if TYPE_CHECKING:
    from olympus_sdk.http import OlympusHttpClient


class DataService:
    """Data query, CRUD, and search operations."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    def query(
        self,
        sql: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a read-only SQL query against the platform data layer.

        Returns rows as a list of column-name-keyed dicts.
        """
        payload: dict[str, Any] = {"sql": sql}
        if params is not None:
            payload["params"] = params
        data = self._http.post("/data/query", json=payload)
        return data.get("rows") or data.get("data") or []

    def insert(self, table: str, record: dict[str, Any]) -> dict[str, Any]:
        """Insert a record into a table."""
        return self._http.post(f"/data/{table}", json=record)

    def update(self, table: str, record_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Update a record by ID."""
        return self._http.patch(f"/data/{table}/{record_id}", json=fields)

    def delete(self, table: str, record_id: str) -> None:
        """Delete a record by ID."""
        self._http.delete(f"/data/{table}/{record_id}")

    def search(
        self,
        query: str,
        *,
        scope: str | None = None,
        limit: int | None = None,
    ) -> list[SearchResult]:
        """Full-text / semantic search across indexed data."""
        payload: dict[str, Any] = {"query": query}
        if scope is not None:
            payload["scope"] = scope
        if limit is not None:
            payload["limit"] = limit
        data = self._http.post("/ai/search", json=payload)
        results_raw = data.get("results") or []
        return [SearchResult.from_dict(r) for r in results_raw]
