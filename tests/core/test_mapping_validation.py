from __future__ import annotations

from typing import Any, cast

from wf_core import Edge, NodeDef, NodeUse, SchemaRef, StateField, StateSchema, Workflow
from wf_core.validation.issues import ValidationIssueCode


def test_validation_allows_nested_node_local_paths() -> None:
    report = _workflow(
        in_map={"input.person.name": "user.name"},
        out_map={"user.age": "state.person.age"},
    ).validate_structure()

    assert report.errors == []


def test_validation_rejects_overlapping_node_input_destinations() -> None:
    report = _workflow(
        in_map={
            "input.person": "user",
            "input.person.name": "user.name",
        },
        out_map={},
    ).validate_structure()

    assert any(
        issue.code == ValidationIssueCode.INVALID_NODE_INPUT_FIELD
        and issue.path == "nodes[0].input"
        and "overlapping node-local input paths" in issue.message
        for issue in report.errors
    )


def test_validation_rejects_overlapping_state_write_destinations() -> None:
    report = _workflow(
        in_map={},
        out_map={
            "user": "state.person",
            "user.age": "state.person.age",
        },
    ).validate_structure()

    assert any(
        issue.code == ValidationIssueCode.INVALID_DESTINATION_PATH
        and issue.path == "nodes[0].output"
        and "overlapping state destination paths" in issue.message
        for issue in report.errors
    )


def test_validation_rejects_invalid_canonical_input_source_path() -> None:
    report = _workflow(
        input=[{"target": "user.name", "path": "state.unknown.name"}],
        output=[],
    ).validate_structure()

    assert any(
        issue.code == ValidationIssueCode.INVALID_SOURCE_PATH
        and issue.path == "nodes[0].input[0].path"
        for issue in report.errors
    )


def test_validation_allows_canonical_input_source_under_declared_state_field_root() -> (
    None
):
    report = _workflow(
        input=[{"target": "user.name", "path": "state.person.name"}],
        output=[],
        state_fields={"person.name": StateField(type="string")},
    ).validate_structure()

    assert not any(
        issue.code == ValidationIssueCode.INVALID_SOURCE_PATH for issue in report.errors
    )


def test_validation_rejects_invalid_canonical_output_destination() -> None:
    workflow = _workflow(
        input=[],
        output=[{"source": "user.name", "target": "state.person.name"}],
    )
    # StatePath parsing rejects bad roots before workflow validation; mutate here so
    # validate_node_use still guards malformed canonical destinations.
    cast(Any, workflow.nodes[0]).output[0].target = "output.person.name"
    report = workflow.validate_structure()

    assert any(
        issue.code == ValidationIssueCode.INVALID_DESTINATION_PATH
        and issue.path == "nodes[0].output[0].target"
        for issue in report.errors
    )


def test_validation_rejects_undeclared_canonical_output_destination_root() -> None:
    report = _workflow(
        input=[],
        output=[{"source": "user.name", "target": "state.unknown.foo"}],
    ).validate_structure()

    assert any(
        issue.code == ValidationIssueCode.INVALID_DESTINATION_PATH
        and issue.path == "nodes[0].output[0].target"
        for issue in report.errors
    )


def test_validation_rejects_overlapping_canonical_input_targets() -> None:
    report = _workflow(
        input=[
            {"target": "user", "value": {"name": "Ada"}},
            {"target": "user.name", "path": "input.person.name"},
        ],
        output=[],
    ).validate_structure()

    assert any(
        issue.code == ValidationIssueCode.INVALID_NODE_INPUT_FIELD
        and issue.path == "nodes[0].input"
        for issue in report.errors
    )


def test_validation_rejects_overlapping_canonical_output_targets() -> None:
    report = _workflow(
        input=[],
        output=[
            {"source": "user", "target": "state.person"},
            {"source": "user.name", "target": "state.person.name"},
        ],
    ).validate_structure()

    assert any(
        issue.code == ValidationIssueCode.INVALID_DESTINATION_PATH
        and issue.path == "nodes[0].output"
        for issue in report.errors
    )


def test_validation_allows_valid_canonical_mapping() -> None:
    report = _workflow(
        input=[
            {"target": "user.name", "path": "input.person.name"},
            {"target": "user.nickname", "value": "Ada"},
        ],
        output=[{"source": "user.age", "target": "state.person.age"}],
    ).validate_structure()

    mapping_issue_codes = {
        ValidationIssueCode.INVALID_NODE_INPUT_FIELD,
        ValidationIssueCode.INVALID_NODE_OUTPUT_FIELD,
        ValidationIssueCode.INVALID_SOURCE_PATH,
        ValidationIssueCode.INVALID_DESTINATION_PATH,
    }
    assert not any(issue.code in mapping_issue_codes for issue in report.errors)


def _workflow(
    *,
    in_map: dict[str, str] | None = None,
    out_map: dict[str, str] | None = None,
    input: list[dict[str, object]] | None = None,
    output: list[dict[str, str]] | None = None,
    state_fields: dict[str, StateField] | None = None,
) -> Workflow:
    node_data: dict[str, object] = {
        "id": "tool",
        "type": "node",
        "node": "tool",
    }
    if input is not None or output is not None:
        node_data["input"] = input or []
        node_data["output"] = output or []
    else:
        node_data["in_map"] = in_map or {}
        node_data["out_map"] = out_map or {}

    return Workflow(
        name="mapping_validation",
        input_schema=SchemaRef.model_validate(
            {"type": "object", "properties": {"person": {"type": "object"}}}
        ),
        state_schema=StateSchema.from_field_map(
            state_fields or {"person": StateField(type="object")}
        ),
        output_schema=SchemaRef(type="object", properties={}),
        node_defs=[
            NodeDef(
                name="tool",
                input_schema=SchemaRef.model_validate(
                    {"type": "object", "properties": {"user": {"type": "object"}}}
                ),
                output_schema=SchemaRef.model_validate(
                    {"type": "object", "properties": {"user": {"type": "object"}}}
                ),
                outcomes=["ok"],
            )
        ],
        start="tool",
        nodes=[NodeUse.model_validate(node_data)],
        edges=[Edge.model_validate({"from": "tool", "outcome": "ok", "to": "__end__"})],
    )
