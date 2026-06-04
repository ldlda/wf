# wf_api Slice 5A/5B Helper Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate duplicated workflow API listing, artifact-plan, source-snapshot, and dependency-summary helpers into protocol-neutral `wf_api` modules without changing public payloads.

**Architecture:** Slice 5A moves workflow list helpers out of MCP-named modules for workflow API callers. Slice 5B promotes duplicated private helpers from `wf_api.capabilities`, `wf_api.artifacts`, `wf_api.drafts`, `wf_api.runs`, and `wf_api.deployments` into focused `wf_api` helper modules. `wf_mcp.shared.pagination` stays untouched because proxy/admin code still uses it.

**Tech Stack:** Python 3.14, Pydantic v2, `wf_api`, `wf_artifacts`, `wf_platform.page_items`, pytest, ruff, basedpyright.

---

## Scope

### In Scope

- Create `src/wf_api/listing.py` for `matches_query` and `paged_list_payload`.
- Create `src/wf_api/artifact_plans.py` for `raw_plan_from_artifact`, `plan_field`, and `plan_nodes`.
- Create `src/wf_api/artifact_refs.py` for `artifact_capability_id`.
- Create `src/wf_api/capability_requirements.py` for `required_capability_payloads`, `observed_node_specs`, and `required_capabilities_for_plan`.
- Create `src/wf_api/source_snapshots.py` for deployment/run source snapshot helpers if currently duplicated in `deployments.py` and `runs.py`.
- Update `src/wf_api/{capabilities,artifacts,drafts,runs,deployments}.py` to import the shared helpers.
- Update `src/wf_mcp/workflow_surface/handlers.py` no-store `list_artifacts` fallback to use `wf_api.listing.paged_list_payload`.
- Add focused `wf_api` tests for the promoted helpers.

### Out of Scope

- Do not move or delete `wf_mcp.shared.pagination`; `src/wf_mcp/proxy/tools.py` still uses it.
- Do not move event primitives in this slice.
- Do not delete `wf_mcp.workflow_surface.*` compatibility shims.
- Do not change MCP tool names, response payload shapes, pagination semantics, artifact IDs, or capability IDs.
- Do not move request/response Pydantic models out of `wf_mcp.workflow_surface.models`.

## File Map

| File | Responsibility |
| --- | --- |
| `src/wf_api/listing.py` | Workflow API list filtering and common paged response payloads. |
| `src/wf_api/artifact_plans.py` | Safe extraction of `RawWorkflowPlan` and plan node dictionaries from saved artifacts. |
| `src/wf_api/artifact_refs.py` | Stable workflow artifact capability IDs. |
| `src/wf_api/capability_requirements.py` | Required-capability payloads and observed NodeSpec inventory projection. |
| `src/wf_api/source_snapshots.py` | Serializable source snapshots used by deployment validation and run resume checks. |
| `src/wf_api/__init__.py` | Optional re-exports for public helper symbols. |
| `src/wf_api/capabilities.py` | Remove local duplicates; import shared helpers. |
| `src/wf_api/artifacts.py` | Remove local duplicates; import shared helpers. |
| `src/wf_api/drafts.py` | Remove local duplicates; import shared helpers. |
| `src/wf_api/runs.py` | Remove local `raw_plan_from_artifact`; import shared helpers. |
| `src/wf_api/deployments.py` | Import source snapshot helper if duplicated there. |
| `src/wf_mcp/workflow_surface/handlers.py` | Stop importing workflow list helper from `wf_mcp.shared`. |
| `tests/wf_api/test_listing.py` | Unit tests for query matching and paged payload shape. |
| `tests/wf_api/test_artifact_helpers.py` | Unit tests for plan extraction, artifact refs, and dependency helper outputs. |
| `tests/wf_api/test_import_direction.py` | Existing guard; must continue passing. |

---

## Task 1: Add `wf_api.listing`

**Files:**

- Create: `src/wf_api/listing.py`
- Test: `tests/wf_api/test_listing.py`
- Modify: `src/wf_api/__init__.py`

- [ ] **Step 1: Write focused listing tests**

Create `tests/wf_api/test_listing.py`:

```python
from __future__ import annotations

from wf_api.listing import matches_query, paged_list_payload


def test_matches_query_accepts_empty_or_missing_query() -> None:
    assert matches_query("Alpha", query=None) is True
    assert matches_query("Alpha", query="  ") is True


def test_matches_query_searches_non_none_values_case_insensitively() -> None:
    assert matches_query(None, "Demo Echo", query="echo") is True
    assert matches_query(None, "Demo Echo", query="missing") is False


def test_paged_list_payload_preserves_common_shape() -> None:
    payload = paged_list_payload(
        "nodes",
        [{"name": "a"}, {"name": "b"}, {"name": "c"}],
        cursor=None,
        limit=2,
    )

    assert payload["nodes"] == [{"name": "a"}, {"name": "b"}]
    assert payload["total"] == 3
    assert payload["next_cursor"] is not None
```

- [ ] **Step 2: Run the tests and verify import failure**

Run:

```bash
uv run pytest tests/wf_api/test_listing.py -q
```

Expected: fail because `wf_api.listing` does not exist.

- [ ] **Step 3: Add `src/wf_api/listing.py`**

```python
from __future__ import annotations

from collections.abc import Sequence
from typing import Any, TypeVar

from wf_platform import page_items

T = TypeVar("T")


def matches_query(*values: object, query: str | None) -> bool:
    """Return whether a compact discovery row matches a human search query."""
    if query is None:
        return True
    needle = query.strip().casefold()
    if not needle:
        return True
    return any(needle in str(value).casefold() for value in values if value is not None)


def paged_list_payload(
    key: str,
    items: Sequence[T],
    *,
    cursor: str | None,
    limit: int,
) -> dict[str, Any]:
    """Build the shared workflow API list response shape."""
    page = page_items(items, cursor=cursor, limit=limit)
    return {
        key: list(page.items),
        "next_cursor": page.next_cursor,
        "total": page.total,
    }
```

- [ ] **Step 4: Export helpers from `src/wf_api/__init__.py`**

Add imports:

```python
from .listing import matches_query, paged_list_payload
```

Add to `__all__`:

```python
"matches_query",
"paged_list_payload",
```

- [ ] **Step 5: Run listing tests**

Run:

```bash
uv run pytest tests/wf_api/test_listing.py -q
```

Expected: pass.

---

## Task 2: Route Current Workflow API Listing Calls Through `wf_api.listing`

**Files:**

- Modify: `src/wf_api/capabilities.py`
- Modify: `src/wf_api/artifacts.py`
- Modify: `src/wf_mcp/workflow_surface/handlers.py`
- Test: existing `tests/wf_api/test_capability_api.py`, `tests/wf_api/test_artifact_api.py`

- [ ] **Step 1: Replace local listing helpers in `src/wf_api/capabilities.py`**

Remove local `_matches_query` and `_paged_list_payload`.

Add:

```python
from .listing import matches_query, paged_list_payload
```

Replace calls:

```python
_matches_query(...)
```

with:

```python
matches_query(...)
```

Replace calls:

```python
_paged_list_payload(...)
```

with:

```python
paged_list_payload(...)
```

- [ ] **Step 2: Replace local listing helpers in `src/wf_api/artifacts.py`**

Remove local `_matches_query`, `_paged_list_payload`, the local `TypeVar`, and now-unused `wf_platform.page_items` import.

Add:

```python
from .listing import matches_query, paged_list_payload
```

Replace local helper calls the same way as Task 2 Step 1.

- [ ] **Step 3: Stop workflow handler fallback from importing `wf_mcp.shared` listing**

In `src/wf_mcp/workflow_surface/handlers.py`, replace:

```python
from ..shared import paged_list_payload
```

with:

```python
from wf_api.listing import paged_list_payload
```

The no-store fallback must keep returning:

```python
return paged_list_payload("nodes", [], cursor=cursor, limit=limit)
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run pytest tests/wf_api/test_listing.py tests/wf_api/test_capability_api.py tests/wf_api/test_artifact_api.py tests/wf_api/test_import_direction.py -q
```

Expected: pass.

---

## Task 3: Add Artifact Plan And Artifact Ref Helpers

**Files:**

- Create: `src/wf_api/artifact_plans.py`
- Create: `src/wf_api/artifact_refs.py`
- Test: `tests/wf_api/test_artifact_helpers.py`

- [ ] **Step 1: Add failing tests for artifact helper behavior**

Create `tests/wf_api/test_artifact_helpers.py` with the imports below. If a helper fixture for artifacts already exists in nearby tests, use it; otherwise construct the minimal `WorkflowArtifact` inline with valid fields copied from existing `tests/wf_api/test_artifact_api.py`.

```python
from __future__ import annotations

import pytest

from wf_api.artifact_plans import plan_field, plan_nodes, raw_plan_from_artifact
from wf_api.artifact_refs import artifact_capability_id


def test_artifact_capability_id_uses_workflow_ref_shape(echo_artifact) -> None:
    assert artifact_capability_id(echo_artifact) == (
        f"workflow.{echo_artifact.id}.v{echo_artifact.version}"
    )


def test_raw_plan_from_artifact_preserves_required_plan_fields(echo_artifact) -> None:
    plan = raw_plan_from_artifact(echo_artifact)

    assert plan.name == echo_artifact.plan["name"]
    assert plan.start == echo_artifact.plan["start"]
    assert len(plan.nodes) == len(echo_artifact.plan["nodes"])


def test_plan_field_reports_missing_field(echo_artifact) -> None:
    broken = echo_artifact.model_copy(
        update={"plan": {key: value for key, value in echo_artifact.plan.items() if key != "start"}}
    )

    with pytest.raises(ValueError, match="missing plan field 'start'"):
        plan_field(broken, "start")


def test_plan_nodes_returns_only_dict_nodes(echo_artifact) -> None:
    artifact = echo_artifact.model_copy(
        update={"plan": {**echo_artifact.plan, "nodes": [{"id": "a"}, "bad"]}}
    )

    assert plan_nodes(artifact) == [{"id": "a"}]
```

If there is no reusable `echo_artifact` fixture, add a private helper in this test file instead of importing fixtures across packages.

- [ ] **Step 2: Run the tests and verify import failure**

Run:

```bash
uv run pytest tests/wf_api/test_artifact_helpers.py -q
```

Expected: fail because modules do not exist.

- [ ] **Step 3: Create `src/wf_api/artifact_refs.py`**

```python
from __future__ import annotations

from wf_artifacts import WorkflowArtifact, WorkflowCapabilityRef


def artifact_capability_id(artifact: WorkflowArtifact) -> str:
    """Return the stable workflow capability name for a saved artifact."""
    return str(
        WorkflowCapabilityRef(
            artifact_id=artifact.id,
            version=artifact.version,
        )
    )
```

- [ ] **Step 4: Create `src/wf_api/artifact_plans.py`**

```python
from __future__ import annotations

from typing import Any

from wf_artifacts import WorkflowArtifact

from .models import RawWorkflowPlan


def raw_plan_from_artifact(artifact: WorkflowArtifact) -> RawWorkflowPlan:
    """Validate the stored raw workflow plan shape expected by runtime calls."""
    return RawWorkflowPlan.model_validate(
        {
            "name": plan_field(artifact, "name"),
            "input_schema": plan_field(artifact, "input_schema"),
            "state_schema": plan_field(artifact, "state_schema"),
            "output_schema": plan_field(artifact, "output_schema"),
            "outcomes": artifact.plan.get("outcomes", ["ok"]),
            "output": artifact.plan.get("output", []),
            "start": plan_field(artifact, "start"),
            "nodes": plan_field(artifact, "nodes"),
            "edges": plan_field(artifact, "edges"),
        }
    )


def plan_field(artifact: WorkflowArtifact, field_name: str) -> Any:
    """Return one required raw-plan field with an artifact-specific error."""
    try:
        return artifact.plan[field_name]
    except KeyError as exc:
        raise ValueError(
            f"workflow artifact {artifact.id}@{artifact.version} "
            f"is missing plan field {field_name!r}"
        ) from exc


def plan_nodes(artifact: WorkflowArtifact) -> list[dict[str, Any]]:
    """Return only dict-shaped node entries from a saved raw plan."""
    nodes = artifact.plan.get("nodes", [])
    return [node for node in nodes if isinstance(node, dict)]
```

- [ ] **Step 5: Export helper modules if desired**

In `src/wf_api/__init__.py`, export only stable helper names if the package already re-exports helpers. If the file is intentionally selective, skip this step and keep imports module-qualified.

- [ ] **Step 6: Run helper tests**

Run:

```bash
uv run pytest tests/wf_api/test_artifact_helpers.py -q
```

Expected: pass.

---

## Task 4: Replace Duplicate Artifact Plan/Ref Helpers In Domain APIs

**Files:**

- Modify: `src/wf_api/capabilities.py`
- Modify: `src/wf_api/artifacts.py`
- Modify: `src/wf_api/runs.py`
- Test: existing capability/artifact/run API tests

- [ ] **Step 1: Update `src/wf_api/capabilities.py` imports**

Add:

```python
from .artifact_plans import raw_plan_from_artifact
from .artifact_refs import artifact_capability_id
```

Remove local `_raw_plan_from_artifact`, `_plan_field`, and `_artifact_capability_id`.

Replace:

```python
_raw_plan_from_artifact(...)
_artifact_capability_id(...)
```

with:

```python
raw_plan_from_artifact(...)
artifact_capability_id(...)
```

- [ ] **Step 2: Update `src/wf_api/artifacts.py` imports**

Add:

```python
from .artifact_plans import plan_nodes
from .artifact_refs import artifact_capability_id
```

Remove local `_plan_nodes` and `_artifact_capability_id`.

Replace calls with `plan_nodes(...)` and `artifact_capability_id(...)`.

- [ ] **Step 3: Update `src/wf_api/runs.py` imports**

Add:

```python
from .artifact_plans import raw_plan_from_artifact
```

Remove local `_raw_plan_from_artifact` and `_plan_field`.

Replace calls with `raw_plan_from_artifact(...)`.

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run pytest tests/wf_api/test_artifact_helpers.py tests/wf_api/test_capability_api.py tests/wf_api/test_artifact_api.py tests/wf_api/test_run_api.py tests/wf_api/test_import_direction.py -q
```

Expected: pass.

---

## Task 5: Add Shared Capability Requirement Helpers

**Files:**

- Create: `src/wf_api/capability_requirements.py`
- Modify: `src/wf_api/drafts.py`
- Modify: `src/wf_api/artifacts.py`
- Modify: `src/wf_api/capabilities.py`
- Test: `tests/wf_api/test_artifact_helpers.py`

- [ ] **Step 1: Add tests for requirement payload and observed specs**

Append to `tests/wf_api/test_artifact_helpers.py`:

```python
from wf_api.capability_requirements import (
    observed_node_specs,
    required_capability_payloads,
)


def test_required_capability_payloads_sorts_by_name(required_capabilities) -> None:
    payload = required_capability_payloads(required_capabilities)

    assert list(payload) == sorted(required_capabilities)
    first = next(iter(payload.values()))
    assert "ref" in first
    assert "kind" in first


def test_observed_node_specs_projects_enabled_context_specs(operation_context) -> None:
    observed = observed_node_specs(operation_context)

    assert isinstance(observed, dict)
    assert all(hasattr(detail, "name") for detail in observed.values())
```

If `required_capabilities` or `operation_context` fixtures do not exist, create explicit local helpers by copying the smallest valid setup from `tests/wf_api/test_artifact_api.py` or `tests/wf_api/test_capability_api.py`. Do not import private helpers from production modules.

- [ ] **Step 2: Create `src/wf_api/capability_requirements.py`**

```python
from __future__ import annotations

from typing import Any

from wf_artifacts import (
    RequiredCapability,
    WorkflowArtifact,
    create_workflow_artifact_from_plan as build_workflow_artifact_from_plan,
)
from wf_platform import CapabilityRef, NodeSpecInventory

from .artifact_plans import plan_nodes
from .operation_context import WorkflowOperationContext


def required_capability_payloads(
    requirements: dict[str, RequiredCapability],
) -> dict[str, dict[str, Any]]:
    """Return deterministic JSON payloads for required capabilities."""
    return {
        name: capability.model_dump(mode="json")
        for name, capability in sorted(requirements.items())
    }


def observed_node_specs(
    context: WorkflowOperationContext,
) -> dict[str, NodeSpecInventory]:
    """Project current executable specs into serializable observed contracts."""
    observed: dict[str, NodeSpecInventory] = {}
    for source in context.capability_sources.values():
        inventory = source.as_inventory()
        observed.update(
            {detail.name: detail for detail in inventory.capabilities.node_spec_details}
        )
    return observed


def required_capabilities_for_plan(
    plan: dict[str, Any],
    *,
    source_bindings: dict[str, str] | None,
    context: WorkflowOperationContext,
) -> dict[str, RequiredCapability]:
    """Infer a draft dependency summary without persisting an artifact."""
    artifact = build_workflow_artifact_from_plan(
        artifact_id="draft_preview",
        version=1,
        title="Draft Preview",
        plan=plan,
        outcomes=("completed",),
        source_bindings=source_bindings,
        observed_node_specs=observed_node_specs(context),
    )
    requirements = artifact.required_capability_map()
    for node in plan_nodes(artifact):
        raw_ref = node.get("node")
        if not isinstance(raw_ref, str) or raw_ref in requirements:
            continue
        try:
            parsed = CapabilityRef.parse(raw_ref)
        except ValueError:
            continue
        requirements[raw_ref] = RequiredCapability(
            ref=parsed,
            kind="node_spec",
        )
    return requirements
```

- [ ] **Step 3: Update `src/wf_api/drafts.py`**

Import:

```python
from .capability_requirements import (
    observed_node_specs,
    required_capabilities_for_plan,
    required_capability_payloads,
)
```

Replace:

```python
_required_capability_payloads(...)
_required_capabilities_for_plan(...)
_observed_node_specs(...)
```

with:

```python
required_capability_payloads(...)
required_capabilities_for_plan(...)
observed_node_specs(...)
```

Remove local `_required_capabilities_for_plan`, `_required_capability_payloads`, `_observed_node_specs`, and `_plan_nodes` if no longer used.

- [ ] **Step 4: Update `src/wf_api/artifacts.py`**

Import:

```python
from .capability_requirements import (
    observed_node_specs,
    required_capability_payloads,
)
```

Replace local helper calls and remove local duplicate helper definitions.

- [ ] **Step 5: Update `src/wf_api/capabilities.py`**

Import:

```python
from .capability_requirements import required_capability_payloads
```

Replace local helper calls and remove the local duplicate helper definition.

- [ ] **Step 6: Run focused tests**

Run:

```bash
uv run pytest tests/wf_api/test_artifact_helpers.py tests/wf_api/test_drafts_service.py tests/wf_api/test_artifact_api.py tests/wf_api/test_capability_api.py tests/wf_api/test_import_direction.py -q
```

Expected: pass.

---

## Task 6: Add Source Snapshot Helper If Duplicated

**Files:**

- Create: `src/wf_api/source_snapshots.py`
- Modify: `src/wf_api/deployments.py`
- Modify: `src/wf_api/runs.py`
- Test: existing deployment/run API tests

- [ ] **Step 1: Inspect current source snapshot helper names**

Run:

```bash
rg -n "_available_sources|AvailableSource|AvailableCapability|capability_name" src/wf_api src/wf_mcp/workflow_surface
```

Expected: identify whether `_available_sources` still exists in `src/wf_api/deployments.py` and is imported by `src/wf_api/runs.py`.

- [ ] **Step 2: Create `src/wf_api/source_snapshots.py` only if a helper exists**

If `_available_sources` exists, move it as:

```python
from __future__ import annotations

from collections.abc import Mapping

from wf_artifacts import AvailableCapability, AvailableSource
from wf_platform import CapabilitySource


def available_sources_from_capability_sources(
    sources: Mapping[str, CapabilitySource],
) -> dict[str, AvailableSource]:
    """Project live capability sources into pinned resume-validation snapshots."""
    return {
        source_id: AvailableSource(
            id=source.id,
            capabilities={
                name: AvailableCapability(name=name)
                for name in source.capabilities.node_specs
            },
        )
        for source_id, source in sources.items()
    }
```

If the existing helper carries more fields than `name`, preserve those fields exactly. Do not simplify the payload.

- [ ] **Step 3: Update deployment/run imports**

Replace duplicated or cross-domain imports with:

```python
from .source_snapshots import available_sources_from_capability_sources
```

Use it wherever resume/deployment validation needs current source snapshots.

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run pytest tests/wf_api/test_deployment_api.py tests/wf_api/test_run_api.py tests/wf_api/test_import_direction.py -q
```

Expected: pass.

---

## Task 7: Remove Duplicate Private Helpers And Guard Imports

**Files:**

- Modify: `src/wf_api/capabilities.py`
- Modify: `src/wf_api/artifacts.py`
- Modify: `src/wf_api/drafts.py`
- Modify: `src/wf_api/runs.py`
- Modify: `src/wf_api/deployments.py`
- Test: import-direction guard

- [ ] **Step 1: Search for leftover duplicated helpers**

Run:

```bash
rg -n "def _matches_query|def _paged_list_payload|def _raw_plan_from_artifact|def _plan_field|def _artifact_capability_id|def _required_capability_payloads|def _observed_node_specs|def _plan_nodes|def _available_sources" src/wf_api src/wf_mcp/workflow_surface
```

Expected:

- No duplicate helper definitions in domain API modules.
- `src/wf_mcp/shared/listing.py` may still define `matches_query` and `paged_list_payload`; leave it alone unless no MCP code imports it.
- `src/wf_mcp/shared/pagination.py` must remain.

- [ ] **Step 2: Search for forbidden workflow listing import**

Run:

```bash
rg -n "from \.\.shared import paged_list_payload|from wf_mcp.shared import paged_list_payload" src/wf_mcp/workflow_surface src/wf_api
```

Expected: no matches.

- [ ] **Step 3: Verify `wf_api` still imports no `wf_mcp`**

Run:

```bash
uv run pytest tests/wf_api/test_import_direction.py -q
```

Expected: pass.

---

## Task 8: Final Verification

**Files:**

- All touched files.

- [ ] **Step 1: Run focused wf_api workflow tests**

Run:

```bash
uv run pytest tests/wf_api/test_listing.py tests/wf_api/test_artifact_helpers.py tests/wf_api/test_drafts_service.py tests/wf_api/test_artifact_api.py tests/wf_api/test_deployment_api.py tests/wf_api/test_run_api.py tests/wf_api/test_capability_api.py tests/wf_api/test_import_direction.py -q
```

Expected: pass.

- [ ] **Step 2: Run adapter-focused workflow surface tests**

Run:

```bash
uv run pytest tests/wf_mcp/workflow_surface tests/wf_mcp/test_server.py -q
```

Expected: pass. If `tests/wf_mcp/workflow_surface` does not exist in this checkout, run the nearest existing workflow-surface test files discovered with `rg -n "WorkflowSurfaceHandlers|register_workflow_tools" tests/wf_mcp`.

- [ ] **Step 3: Run lint and type checks**

Run:

```bash
uv run ruff check src/wf_api src/wf_mcp/workflow_surface tests/wf_api
uv run ruff format --check src/wf_api src/wf_mcp/workflow_surface tests/wf_api
uv run basedpyright --level error
```

Expected: all pass with zero new diagnostics.

- [ ] **Step 4: Optional full suite**

Run:

```bash
uv run pytest -q
```

Expected: existing suite status remains at least as good as before this slice.

---

## Handoff Report Requirements

When done, report:

- Files created.
- Files modified.
- Exact helpers moved and their new canonical module.
- Any helpers intentionally left in place and why.
- Verification commands and outputs.
- Any deviations from this plan.

## Self-Review

- Spec coverage: covers roadmap Slice 5 listing cleanup and post-Slice-4 helper promotion. Event primitives are explicitly deferred because their semantics are larger than this helper cleanup.
- Placeholder scan: no `TBD`, no unspecified edge handling, no “write tests for above” without concrete examples.
- Type consistency: helper names are stable and public names omit leading underscores; domain modules should import from `wf_api.*`, never `wf_mcp.*`.
