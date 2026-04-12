"""AI Agent Workflow Orchestration client — wraps /agent-workflows/* routes (#2915).

Distinct from ``WorkflowsService`` which handles marketplace templates.
See ``olympus-cloud-gcp`` issue #2915 for full architecture.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from olympus_sdk.http import OlympusHttpClient


class AgentWorkflowsService:
    """Tenant-scoped multi-agent DAG workflows (#2915).

    A workflow is a directed acyclic graph of agent nodes. Each node invokes
    an agent from the tenant's registry. Triggers can be manual, cron-based
    (via Cloud Scheduler), or event-driven (order.created, inventory.low, …).

    Free tier: 100 executions, 1000 agent messages, 10k D1 queries per month.
    """

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def list(
        self,
        *,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """List workflows for the current tenant.

        ``status`` filters by ``draft``, ``active``, ``paused``, ``archived``.
        """
        params: dict[str, Any] = {}
        if status is not None:
            params["status"] = status
        if limit is not None:
            params["limit"] = limit
        data = self._http.get("/agent-workflows", params=params)
        return data.get("workflows") or data.get("data") or []

    def get(self, workflow_id: str) -> dict[str, Any]:
        """Get a single workflow by ID with its full DAG schema."""
        return self._http.get(f"/agent-workflows/{workflow_id}")

    def create(
        self,
        *,
        name: str,
        schema: dict[str, Any],
        description: str | None = None,
        triggers: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Create a new workflow.

        ``schema`` is the DAG definition with ``nodes`` and ``edges``.
        ``triggers`` is a list of trigger configs (cron / event / manual).
        """
        payload: dict[str, Any] = {"name": name, "schema": schema}
        if description is not None:
            payload["description"] = description
        if triggers is not None:
            payload["triggers"] = triggers
        return self._http.post("/agent-workflows", json=payload)

    def update(
        self,
        workflow_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        """Update an existing workflow. Pass only fields to change."""
        return self._http.put(f"/agent-workflows/{workflow_id}", json=updates)

    def delete(self, workflow_id: str) -> None:
        """Soft-delete (archive) a workflow."""
        self._http.delete(f"/agent-workflows/{workflow_id}")

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(
        self,
        workflow_id: str,
        *,
        input: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Manually trigger a workflow execution. Returns execution ID —
        poll :meth:`get_execution` for results.
        """
        payload: dict[str, Any] = {}
        if input is not None:
            payload["input"] = input
        return self._http.post(f"/agent-workflows/{workflow_id}/execute", json=payload)

    def list_executions(
        self,
        workflow_id: str,
        *,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """List execution history for a workflow."""
        params: dict[str, Any] = {}
        if status is not None:
            params["status"] = status
        if limit is not None:
            params["limit"] = limit
        data = self._http.get(
            f"/agent-workflows/{workflow_id}/executions", params=params
        )
        return data.get("executions") or data.get("data") or []

    def get_execution(self, execution_id: str) -> dict[str, Any]:
        """Get full execution detail including per-step results."""
        return self._http.get(f"/agent-workflow-executions/{execution_id}")

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------

    def set_schedule(
        self,
        workflow_id: str,
        cron_expression: str,
    ) -> dict[str, Any]:
        """Set or update the cron schedule for a workflow.

        ``cron_expression`` follows standard cron: ``minute hour day month weekday``.
        """
        return self._http.post(
            f"/agent-workflows/{workflow_id}/schedule",
            json={"cron_expression": cron_expression},
        )

    def remove_schedule(self, workflow_id: str) -> None:
        """Remove the cron schedule from a workflow."""
        self._http.delete(f"/agent-workflows/{workflow_id}/schedule")

    # ------------------------------------------------------------------
    # Usage metering
    # ------------------------------------------------------------------

    def usage(self) -> dict[str, Any]:
        """Get current month usage vs tenant tier limits."""
        return self._http.get("/agent-workflows/usage")
