from __future__ import annotations

from typing import Any, cast

from wf_artifacts import RequiredCapability, create_workflow_artifact_from_plan
from wf_platform import NodeSpecInventory


def test_create_workflow_artifact_from_plan_derives_boundary_schemas() -> None:
    artifact = create_workflow_artifact_from_plan(
        artifact_id="echo",
        version=1,
        title="Echo",
        description="Echo through a saved plan.",
        plan=_plan(),
        outcomes=("done",),
        required_capabilities={
            "demo.echo_tool": RequiredCapability(
                ref="demo.echo_tool",
                kind="node_spec",
            )
        },
        created_from_catalog_version="catalog-1",
    )

    assert artifact.id == "echo"
    assert artifact.kind == "workflow"
    assert artifact.version == 1
    assert artifact.title == "Echo"
    assert artifact.input_schema["properties"]["text"]["type"] == "string"
    assert artifact.output_schema["properties"]["echoed"]["type"] == "string"
    assert artifact.outcomes == ("done",)
    assert artifact.plan["name"] == "echo"
    assert "demo.echo_tool" in artifact.required_capability_map()
    assert artifact.created_from_catalog_version == "catalog-1"


def test_create_workflow_artifact_from_plan_adds_reducer_dependencies() -> None:
    plan = _plan()
    plan["state_schema"] = {
        "type": "object",
        "properties": {"best_score": {"type": "integer", "reducer": "wf.std.max"}},
    }

    artifact = create_workflow_artifact_from_plan(
        artifact_id="score",
        version=1,
        title="Score",
        plan=plan,
        outcomes=("done",),
    )

    reducer = artifact.required_capability_map()["wf.std.max"]
    assert reducer.logical_source == "wf.std"
    assert reducer.capability_name == "max"
    assert reducer.kind == "reducer"


def test_create_workflow_artifact_from_plan_rewrites_bound_node_specs() -> None:
    plan = _plan()
    _set_first_node_ref(plan, "demo.personal.echo_tool")

    artifact = create_workflow_artifact_from_plan(
        artifact_id="echo",
        version=1,
        title="Echo",
        plan=plan,
        outcomes=("done",),
        source_bindings={"demo": "demo.personal"},
    )

    node = artifact.plan["nodes"][0]
    required = artifact.required_capability_map()["demo.echo_tool"]
    assert node["node"] == "demo.echo_tool"
    assert required.logical_source == "demo"
    assert required.capability_name == "echo_tool"
    assert required.kind == "node_spec"
    assert str(required.observed_concrete_source) == "demo.personal"


def test_create_workflow_artifact_from_plan_snapshots_observed_node_spec() -> None:
    plan = _plan()
    _set_first_node_ref(plan, "demo.personal.echo_tool")

    artifact = create_workflow_artifact_from_plan(
        artifact_id="echo",
        version=1,
        title="Echo",
        plan=plan,
        outcomes=("done",),
        source_bindings={"demo": "demo.personal"},
        observed_node_specs={
            "demo.personal.echo_tool": NodeSpecInventory(
                name="demo.personal.echo_tool",
                outcomes=("ok",),
                input_schema={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                },
                output_schema={
                    "type": "object",
                    "properties": {"echoed": {"type": "string"}},
                },
                is_async=False,
                accepts_context=False,
            )
        },
    )

    required = artifact.required_capability_map()["demo.echo_tool"]
    assert required.input_schema_snapshot == {
        "type": "object",
        "properties": {"text": {"type": "string"}},
    }
    assert required.output_schema_snapshot == {
        "type": "object",
        "properties": {"echoed": {"type": "string"}},
    }
    assert required.input_schema_hash is not None
    assert required.output_schema_hash is not None


def test_create_workflow_artifact_from_plan_keeps_explicit_capability_metadata() -> (
    None
):
    plan = _plan()
    _set_first_node_ref(plan, "demo.personal.echo_tool")

    artifact = create_workflow_artifact_from_plan(
        artifact_id="echo",
        version=1,
        title="Echo",
        plan=plan,
        outcomes=("done",),
        source_bindings={"demo": "demo.personal"},
        required_capabilities={
            "demo.echo_tool": RequiredCapability(
                ref="demo.echo_tool",
                kind="node_spec",
                input_schema_hash="sha256:explicit",
            )
        },
    )

    required = artifact.required_capability_map()["demo.echo_tool"]
    assert required.input_schema_hash == "sha256:explicit"


def test_create_workflow_artifact_from_plan_accepts_wrapper_kind() -> None:
    artifact = create_workflow_artifact_from_plan(
        artifact_id="normalize_status",
        version=1,
        title="Normalize Status",
        plan=_plan(),
        outcomes=("done",),
        kind="wrapper",
    )

    assert artifact.kind == "wrapper"


def test_create_workflow_artifact_from_plan_rejects_missing_boundary_schema() -> None:
    plan = _plan()
    plan.pop("output_schema")

    try:
        create_workflow_artifact_from_plan(
            artifact_id="echo",
            version=1,
            title="Echo",
            plan=plan,
            outcomes=("done",),
        )
    except ValueError as exc:
        assert "output_schema" in str(exc)
    else:
        raise AssertionError("expected missing output_schema to be rejected")


def test_create_workflow_artifact_from_plan_rejects_invalid_workflow_shape() -> None:
    plan = _plan()
    plan["state_schema"] = {"type": 123}

    try:
        create_workflow_artifact_from_plan(
            artifact_id="echo",
            version=1,
            title="Echo",
            plan=plan,
            outcomes=("done",),
        )
    except ValueError as exc:
        assert "state_schema" in str(exc)
        assert "type" in str(exc)
    else:
        raise AssertionError("expected invalid state schema to be rejected")


def test_create_workflow_artifact_from_plan_rejects_missing_start_node() -> None:
    plan = _plan()
    plan["start"] = "missing"

    try:
        create_workflow_artifact_from_plan(
            artifact_id="echo",
            version=1,
            title="Echo",
            plan=plan,
            outcomes=("done",),
        )
    except ValueError as exc:
        assert "start node 'missing' does not exist" in str(exc)
    else:
        raise AssertionError("expected missing start node to be rejected")


def _plan() -> dict[str, object]:
    return {
        "name": "echo",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        "state_schema": {"fields": {"echoed": {"type": "string"}}},
        "output_schema": {
            "type": "object",
            "properties": {"echoed": {"type": "string"}},
            "required": ["echoed"],
        },
        "start": "echo",
        "nodes": [
            {
                "id": "echo",
                "type": "node",
                "node": "demo.echo_tool",
                "in_map": {"input.text": "text"},
                "out_map": {"echoed": "state.echoed"},
            }
        ],
        "edges": [{"from": "echo", "outcome": "ok", "to": "__end__"}],
    }


def _set_first_node_ref(plan: dict[str, object], node_ref: str) -> None:
    """Set the first node ref in a loosely typed raw plan test fixture."""
    nodes = cast("list[dict[str, Any]]", plan["nodes"])
    nodes[0]["node"] = node_ref
