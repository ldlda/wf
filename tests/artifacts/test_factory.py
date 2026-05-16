from __future__ import annotations

from wf_artifacts import RequiredCapability, create_workflow_artifact_from_plan


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
                logical_source="demo",
                capability_name="echo_tool",
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
    assert "demo.echo_tool" in artifact.required_capabilities
    assert artifact.created_from_catalog_version == "catalog-1"


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
    plan["state_schema"] = {"fields": {"echoed": {"schema": {"type": "string"}}}}

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
