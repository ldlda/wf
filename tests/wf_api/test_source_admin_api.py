from __future__ import annotations

import asyncio
from typing import Any

import pytest

from wf_api import WorkflowSourceAdminApi, WorkflowSourceAdminSurface
from wf_api.models import RawWorkflowPlan
from wf_api.operation_context import WorkflowOperationContext
from wf_api.saved_subgraphs import SavedSubgraphTree
from wf_artifacts import WorkflowArtifact, WorkflowDeployment
from wf_authoring import NodeSpec
from wf_core import RunState
from wf_platform import (
    CapabilityBuckets,
    CapabilitySource,
    SourcePermissions,
    SourceVisibility,
)


class DummyEvents:
    def record_event(self, event: object) -> None:
        pass

    def record_workflow_event(
        self,
        event_type: str,
        *,
        capability_id: str,
        payload: dict[str, Any],
    ) -> None:
        pass


class DummyRuntime:
    async def run_workflow_from_plan(
        self,
        plan: RawWorkflowPlan,
        workflow_input: dict[str, Any],
        deployment: WorkflowDeployment | None = None,
        artifact: WorkflowArtifact | None = None,
        saved_subgraph_tree: SavedSubgraphTree | None = None,
    ) -> RunState:
        raise AssertionError("source admin tests must not run workflows")

    async def resume_workflow_from_plan(
        self,
        plan: RawWorkflowPlan,
        run: RunState,
        *,
        resume_payload: dict[str, Any],
        resume_outcome: str,
        deployment: WorkflowDeployment | None = None,
        artifact: WorkflowArtifact | None = None,
        saved_subgraph_tree: SavedSubgraphTree | None = None,
    ) -> RunState:
        raise AssertionError("source admin tests must not resume workflows")


class StaticSpecProvider:
    def __init__(self, sources: dict[str, CapabilitySource]) -> None:
        self._sources = sources

    @property
    def capability_sources(self) -> dict[str, CapabilitySource]:
        return self._sources

    def get_qualified_spec(self, qualified_name: str) -> NodeSpec[Any, Any]:
        raise KeyError(f"unknown capability {qualified_name!r}")


def _api(*sources: CapabilitySource) -> WorkflowSourceAdminApi:
    provider = StaticSpecProvider({source.id: source for source in sources})
    return WorkflowSourceAdminApi(
        WorkflowOperationContext(
            artifact_store=None,
            draft_workspace_store=None,
            run_store=None,
            events=DummyEvents(),
            specs=provider,
            runtime=DummyRuntime(),
            live_sources=None,
        )
    )


def _source(source_id: str, *, enabled: bool = True) -> CapabilitySource:
    return CapabilitySource(
        id=source_id,
        kind="connection",
        enabled=enabled,
        capabilities=CapabilityBuckets(),
        visibility=SourceVisibility(
            planner=True,
            mcp_client=True,
            admin_dashboard=True,
        ),
        permissions=SourcePermissions(calls_upstream=True),
        description=f"{source_id} source",
    )


def test_source_admin_lists_compact_sources_in_id_order() -> None:
    api = _api(_source("zeta.personal"), _source("alpha.personal", enabled=False))

    payload = asyncio.run(api.list_sources(limit=10))

    assert payload["total"] == 2
    assert payload["next_cursor"] is None
    assert [source["id"] for source in payload["sources"]] == [
        "alpha.personal",
        "zeta.personal",
    ]
    assert payload["sources"][0]["enabled"] is False
    assert payload["sources"][1]["description"] == "zeta.personal source"


def test_source_admin_pages_sources() -> None:
    api = _api(_source("a"), _source("b"), _source("c"))

    first = asyncio.run(api.list_sources(limit=2))
    second = asyncio.run(api.list_sources(cursor=first["next_cursor"], limit=2))

    assert [source["id"] for source in first["sources"]] == ["a", "b"]
    assert first["next_cursor"] == "2"
    assert [source["id"] for source in second["sources"]] == ["c"]
    assert second["next_cursor"] is None


def test_source_admin_inspects_full_source_inventory() -> None:
    api = _api(_source("demo.personal"))

    payload = asyncio.run(api.inspect_source(source_id="demo.personal"))

    assert payload["id"] == "demo.personal"
    assert payload["kind"] == "connection"
    assert payload["description"] == "demo.personal source"
    assert payload["visibility"]["planner"] is True
    assert payload["permissions"]["calls_upstream"] is True


def test_source_admin_inspect_unknown_source_raises_clear_key_error() -> None:
    api = _api(_source("demo.personal"))

    with pytest.raises(KeyError, match="unknown source 'missing.source'"):
        asyncio.run(api.inspect_source(source_id="missing.source"))


def test_source_admin_api_satisfies_surface_protocol() -> None:
    api: WorkflowSourceAdminSurface = _api(_source("demo.personal"))

    assert api is not None
