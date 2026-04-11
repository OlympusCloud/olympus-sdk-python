"""Business intelligence: revenue, staff, insights, and comparisons.

Wraps the Olympus Business Revolution (Rex AI COO) analytics via the Go API Gateway.
Routes: ``/business/*``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from olympus_sdk.http import OlympusHttpClient


class BusinessService:
    """Business intelligence: revenue, staff, insights, and comparisons."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    async def get_revenue_summary(
        self,
        *,
        period: str | None = None,
        location_id: str | None = None,
    ) -> dict:
        """Get a revenue summary for the specified period and location."""
        return self._http.get(
            "/business/revenue/summary",
            params={"period": period, "location_id": location_id},
        )

    async def get_revenue_trends(
        self,
        *,
        period: str | None = None,
        granularity: str | None = None,
        location_id: str | None = None,
    ) -> dict:
        """Get revenue trend data over time."""
        return self._http.get(
            "/business/revenue/trends",
            params={
                "period": period,
                "granularity": granularity,
                "location_id": location_id,
            },
        )

    async def get_top_sellers(
        self,
        *,
        period: str | None = None,
        limit: int | None = None,
        location_id: str | None = None,
    ) -> dict:
        """Get top-selling items for the specified period."""
        return self._http.get(
            "/business/top-sellers",
            params={"period": period, "limit": limit, "location_id": location_id},
        )

    async def get_on_duty_staff(
        self,
        *,
        location_id: str | None = None,
    ) -> dict:
        """Get currently on-duty staff members."""
        return self._http.get(
            "/business/staff/on-duty",
            params={"location_id": location_id},
        )

    async def get_insights(
        self,
        *,
        category: str | None = None,
        period: str | None = None,
    ) -> dict:
        """Get AI-generated business insights."""
        return self._http.get(
            "/business/insights",
            params={"category": category, "period": period},
        )

    async def get_comparisons(
        self,
        *,
        metric: str | None = None,
        period: str | None = None,
        compare_to: str | None = None,
    ) -> dict:
        """Get period-over-period or location-over-location comparisons."""
        return self._http.get(
            "/business/comparisons",
            params={"metric": metric, "period": period, "compare_to": compare_to},
        )
