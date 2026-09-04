from __future__ import annotations

from wf_core import END, Workflow
from wf_core.analysis.control_regions import (
    ControlRegionAnalysis,
    ControlRegionIssueKind,
    analyze_control_regions,
)
from wf_core.validation.issues import ValidationIssueCode


def _workflow(
    *,
    start: str,
    nodes: list[dict[str, object]],
    edges: list[dict[str, str]],
) -> Workflow:
    return Workflow.model_validate(
        {
            "name": "control-regions",
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {
                "type": "object",
                "properties": {
                    "items": {"type": "array", "items": {"type": "string"}},
                    "inner_items": {"type": "array", "items": {"type": "integer"}},
                },
            },
            "output_schema": {"type": "object", "properties": {}},
            "start": start,
            "nodes": nodes,
            "edges": edges,
            "node_defs": [],
        }
    )


def _node(node_id: str) -> dict[str, object]:
    return {"id": node_id, "type": "node", "node": "noop"}


def _foreach(node_id: str, *, alias: str = "item") -> dict[str, object]:
    return {
        "id": node_id,
        "type": "foreach",
        "over": "state.items",
        "as": alias,
        "mode": "serial",
    }


def _condition(node_id: str) -> dict[str, object]:
    return {
        "id": node_id,
        "type": "condition",
        "check": {"op": "exists", "path": "state.items"},
    }


_CONTROL_REGION_CODES = {code.value for code in ControlRegionIssueKind}


def _public_control_errors(workflow: Workflow) -> list[tuple[str, str]]:
    return [
        (issue.code.value, issue.path)
        for issue in workflow.validate_structure().errors
        if issue.code.value in _CONTROL_REGION_CODES
    ]


def _assert_no_public_control_errors(workflow: Workflow) -> None:
    assert _public_control_errors(workflow) == []


def test_closed_root_cycle_has_one_empty_control_region() -> None:
    workflow = _workflow(
        start="a",
        nodes=[_node("a"), _node("b")],
        edges=[
            {"from": "a", "outcome": "ok", "to": "b"},
            {"from": "b", "outcome": "ok", "to": "a"},
        ],
    )

    analysis = analyze_control_regions(workflow)

    assert analysis.issues == ()
    assert analysis.owner_stack_by_node == {"a": (), "b": ()}
    _assert_no_public_control_errors(workflow)


def test_foreach_cycle_with_possible_return_is_valid() -> None:
    workflow = _workflow(
        start="f",
        nodes=[_foreach("f"), _node("a")],
        edges=[
            {"from": "f", "outcome": "loop", "to": "a"},
            {"from": "a", "outcome": "again", "to": "a"},
            {"from": "a", "outcome": "done", "to": "f"},
            {"from": "f", "outcome": "done", "to": END},
        ],
    )

    analysis = analyze_control_regions(workflow)

    assert analysis.issues == ()
    assert analysis.owner_stack_by_node["a"] == ("f",)
    assert analysis.owner_stack_by_node["f"] == ()
    _assert_no_public_control_errors(workflow)


def test_conditional_foreach_paths_can_both_return() -> None:
    workflow = _workflow(
        start="f",
        nodes=[_foreach("f"), _condition("condition"), _node("work")],
        edges=[
            {"from": "f", "outcome": "loop", "to": "condition"},
            {"from": "condition", "outcome": "true", "to": "work"},
            {"from": "condition", "outcome": "false", "to": "f"},
            {"from": "work", "outcome": "ok", "to": "f"},
            {"from": "f", "outcome": "done", "to": END},
        ],
    )

    analysis = analyze_control_regions(workflow)

    assert analysis.issues == ()
    assert analysis.owner_stack_by_node["condition"] == ("f",)
    assert analysis.owner_stack_by_node["work"] == ("f",)
    _assert_no_public_control_errors(workflow)


def test_nested_foreach_assigns_static_owner_stacks() -> None:
    workflow = _workflow(
        start="f1",
        nodes=[
            _foreach("f1"),
            _foreach("f2"),
            _node("work"),
            _node("tail"),
            _node("after"),
        ],
        edges=[
            {"from": "f1", "outcome": "loop", "to": "f2"},
            {"from": "f2", "outcome": "loop", "to": "work"},
            {"from": "work", "outcome": "ok", "to": "f2"},
            {"from": "f2", "outcome": "done", "to": "tail"},
            {"from": "tail", "outcome": "ok", "to": "f1"},
            {"from": "f1", "outcome": "done", "to": "after"},
            {"from": "after", "outcome": "ok", "to": END},
        ],
    )

    analysis: ControlRegionAnalysis = analyze_control_regions(workflow)

    assert analysis.owner_stack_by_node == {
        "f1": (),
        "f2": ("f1",),
        "work": ("f1", "f2"),
        "tail": ("f1",),
        "after": (),
    }
    assert analysis.issues == ()
    _assert_no_public_control_errors(workflow)


def test_reentering_completed_foreach_keeps_one_static_region() -> None:
    workflow = _workflow(
        start="again",
        nodes=[_condition("again"), _foreach("f"), _node("work")],
        edges=[
            {"from": "again", "outcome": "true", "to": "f"},
            {"from": "f", "outcome": "loop", "to": "work"},
            {"from": "work", "outcome": "ok", "to": "f"},
            {"from": "f", "outcome": "done", "to": "again"},
            {"from": "again", "outcome": "false", "to": END},
        ],
    )

    analysis = analyze_control_regions(workflow)

    assert analysis.issues == ()
    assert analysis.owner_stack_by_node["f"] == ()
    assert analysis.owner_stack_by_node["work"] == ("f",)
    assert analysis.owner_stack_by_node["again"] == ()
    _assert_no_public_control_errors(workflow)


def test_external_entry_into_foreach_body_is_region_conflict() -> None:
    workflow = _workflow(
        start="start",
        nodes=[_condition("start"), _foreach("f"), _node("b")],
        edges=[
            {"from": "start", "outcome": "true", "to": "f"},
            {"from": "start", "outcome": "false", "to": "b"},
            {"from": "f", "outcome": "loop", "to": "b"},
            {"from": "b", "outcome": "ok", "to": "f"},
            {"from": "f", "outcome": "done", "to": END},
        ],
    )

    analysis = analyze_control_regions(workflow)

    assert (ControlRegionIssueKind.FOREACH_REGION_CONFLICT, "nodes[b]") in [
        (issue.kind, issue.path) for issue in analysis.issues
    ]
    assert "b" not in analysis.owner_stack_by_node
    matching = [
        issue
        for issue in workflow.validate_structure().errors
        if issue.code == ValidationIssueCode.FOREACH_REGION_CONFLICT
    ]
    assert matching[0].path == "nodes[b]"


def test_foreach_body_escape_is_region_conflict() -> None:
    workflow = _workflow(
        start="f",
        nodes=[_foreach("f"), _node("b"), _node("after")],
        edges=[
            {"from": "f", "outcome": "loop", "to": "b"},
            {"from": "b", "outcome": "ok", "to": "after"},
            {"from": "f", "outcome": "done", "to": "after"},
            {"from": "after", "outcome": "ok", "to": END},
        ],
    )

    analysis = analyze_control_regions(workflow)

    assert (ControlRegionIssueKind.FOREACH_REGION_CONFLICT, "nodes[after]") in [
        (issue.kind, issue.path) for issue in analysis.issues
    ]
    assert "after" not in analysis.owner_stack_by_node
    matching = [
        issue
        for issue in workflow.validate_structure().errors
        if issue.code == ValidationIssueCode.FOREACH_REGION_CONFLICT
    ]
    assert matching[0].path == "nodes[after]"


def test_skipping_inner_foreach_owner_is_invalid_return() -> None:
    workflow = _workflow(
        start="f1",
        nodes=[_foreach("f1"), _foreach("f2"), _node("work")],
        edges=[
            {"from": "f1", "outcome": "loop", "to": "f2"},
            {"from": "f2", "outcome": "loop", "to": "work"},
            {"from": "work", "outcome": "ok", "to": "f1"},
            {"from": "f1", "outcome": "done", "to": END},
            {"from": "f2", "outcome": "done", "to": END},
        ],
    )

    analysis = analyze_control_regions(workflow)

    assert (ControlRegionIssueKind.INVALID_FOREACH_RETURN, "edges[2]") in [
        (issue.kind, issue.path) for issue in analysis.issues
    ]
    matching = [
        issue
        for issue in workflow.validate_structure().errors
        if issue.code == ValidationIssueCode.INVALID_FOREACH_RETURN
    ]
    assert matching[0].path == "edges[2]"


def test_reentering_active_ancestor_foreach_as_nested_controller_is_invalid() -> None:
    workflow = _workflow(
        start="f1",
        nodes=[_foreach("f1"), _foreach("f2")],
        edges=[
            {"from": "f1", "outcome": "loop", "to": "f2"},
            {"from": "f2", "outcome": "loop", "to": "f1"},
            {"from": "f2", "outcome": "done", "to": "f1"},
            {"from": "f1", "outcome": "done", "to": END},
        ],
    )

    analysis = analyze_control_regions(workflow)

    assert (ControlRegionIssueKind.INVALID_FOREACH_RETURN, "edges[1]") in [
        (issue.kind, issue.path) for issue in analysis.issues
    ]
    matching = [
        issue
        for issue in workflow.validate_structure().errors
        if issue.code == ValidationIssueCode.INVALID_FOREACH_RETURN
    ]
    assert matching[0].path == "edges[1]"


def test_entering_sibling_foreach_body_is_region_conflict() -> None:
    workflow = _workflow(
        start="f1",
        nodes=[_foreach("f1"), _foreach("f2"), _node("b1"), _node("b2")],
        edges=[
            {"from": "f1", "outcome": "loop", "to": "b1"},
            {"from": "b1", "outcome": "ok", "to": "b2"},
            {"from": "f2", "outcome": "loop", "to": "b2"},
            {"from": "b2", "outcome": "ok", "to": "f1"},
            {"from": "f1", "outcome": "done", "to": "f2"},
            {"from": "f2", "outcome": "done", "to": END},
        ],
    )

    analysis = analyze_control_regions(workflow)

    assert (ControlRegionIssueKind.FOREACH_REGION_CONFLICT, "nodes[b2]") in [
        (issue.kind, issue.path) for issue in analysis.issues
    ]
    matching = [
        issue
        for issue in workflow.validate_structure().errors
        if issue.code == ValidationIssueCode.FOREACH_REGION_CONFLICT
    ]
    assert matching[0].path == "nodes[b2]"


def test_empty_foreach_body_is_rejected() -> None:
    workflow = _workflow(
        start="f",
        nodes=[_foreach("f")],
        edges=[
            {"from": "f", "outcome": "loop", "to": "f"},
            {"from": "f", "outcome": "done", "to": END},
        ],
    )

    analysis = analyze_control_regions(workflow)

    assert (ControlRegionIssueKind.EMPTY_FOREACH_BODY, "edges[0]") in [
        (issue.kind, issue.path) for issue in analysis.issues
    ]
    matching = [
        issue
        for issue in workflow.validate_structure().errors
        if issue.code == ValidationIssueCode.EMPTY_FOREACH_BODY
    ]
    assert matching[0].path == "edges[0]"


def test_closed_foreach_body_cycle_has_no_return() -> None:
    workflow = _workflow(
        start="f",
        nodes=[_foreach("f"), _node("a"), _node("b")],
        edges=[
            {"from": "f", "outcome": "loop", "to": "a"},
            {"from": "a", "outcome": "ok", "to": "b"},
            {"from": "b", "outcome": "ok", "to": "a"},
            {"from": "f", "outcome": "done", "to": END},
        ],
    )

    analysis = analyze_control_regions(workflow)

    assert (ControlRegionIssueKind.FOREACH_BODY_NO_RETURN, "nodes[f]") in [
        (issue.kind, issue.path) for issue in analysis.issues
    ]
    matching = [
        issue
        for issue in workflow.validate_structure().errors
        if issue.code == ValidationIssueCode.FOREACH_BODY_NO_RETURN
    ]
    assert matching[0].path == "nodes[f]"


def test_foreach_body_cannot_target_end_token() -> None:
    workflow = _workflow(
        start="f",
        nodes=[_foreach("f"), _node("body")],
        edges=[
            {"from": "f", "outcome": "loop", "to": "body"},
            {"from": "body", "outcome": "ok", "to": END},
            {"from": "f", "outcome": "done", "to": END},
        ],
    )

    analysis = analyze_control_regions(workflow)

    assert (ControlRegionIssueKind.INVALID_FOREACH_TERMINAL, "edges[1]") in [
        (issue.kind, issue.path) for issue in analysis.issues
    ]
    matching = [
        issue
        for issue in workflow.validate_structure().errors
        if issue.code == ValidationIssueCode.INVALID_FOREACH_TERMINAL
    ]
    assert matching[0].path == "edges[1]"


def test_foreach_body_cannot_target_explicit_end_node() -> None:
    workflow = _workflow(
        start="f",
        nodes=[
            _foreach("f"),
            _node("body"),
            {"id": "stop", "type": "end", "outcome": "ok"},
        ],
        edges=[
            {"from": "f", "outcome": "loop", "to": "body"},
            {"from": "body", "outcome": "ok", "to": "stop"},
            {"from": "f", "outcome": "done", "to": END},
        ],
    )

    analysis = analyze_control_regions(workflow)

    assert (ControlRegionIssueKind.INVALID_FOREACH_TERMINAL, "edges[1]") in [
        (issue.kind, issue.path) for issue in analysis.issues
    ]
    matching = [
        issue
        for issue in workflow.validate_structure().errors
        if issue.code == ValidationIssueCode.INVALID_FOREACH_TERMINAL
    ]
    assert matching[0].path == "edges[1]"


def test_explicit_end_reached_from_three_regions_stays_conflicted() -> None:
    workflow = _workflow(
        start="start",
        nodes=[
            _node("start"),
            _foreach("f1"),
            _node("b1"),
            _foreach("f2"),
            _node("b2"),
            {"id": "stop", "type": "end", "outcome": "ok"},
        ],
        edges=[
            {"from": "start", "outcome": "direct", "to": "stop"},
            {"from": "start", "outcome": "left", "to": "f1"},
            {"from": "start", "outcome": "right", "to": "f2"},
            {"from": "f1", "outcome": "loop", "to": "b1"},
            {"from": "b1", "outcome": "ok", "to": "stop"},
            {"from": "f1", "outcome": "done", "to": END},
            {"from": "f2", "outcome": "loop", "to": "b2"},
            {"from": "b2", "outcome": "ok", "to": "stop"},
            {"from": "f2", "outcome": "done", "to": END},
        ],
    )

    analysis = analyze_control_regions(workflow)

    conflicts = [
        issue
        for issue in analysis.issues
        if issue.kind == ControlRegionIssueKind.FOREACH_REGION_CONFLICT
        and issue.path == "nodes[stop]"
    ]
    assert len(conflicts) == 1
    assert "stop" not in analysis.owner_stack_by_node


def test_every_unreachable_node_is_reported() -> None:
    workflow = _workflow(
        start="work",
        nodes=[_node("work"), _node("detached_a"), _node("detached_b")],
        edges=[
            {"from": "work", "outcome": "ok", "to": END},
            {"from": "detached_a", "outcome": "ok", "to": "detached_b"},
            {"from": "detached_b", "outcome": "ok", "to": "detached_a"},
        ],
    )

    analysis = analyze_control_regions(workflow)
    by_kind_path = [(issue.kind, issue.path) for issue in analysis.issues]

    assert (
        ControlRegionIssueKind.UNREACHABLE_NODE,
        "nodes[detached_a]",
    ) in by_kind_path
    assert (
        ControlRegionIssueKind.UNREACHABLE_NODE,
        "nodes[detached_b]",
    ) in by_kind_path
    public_by_code_path = [
        (issue.code.value, issue.path) for issue in workflow.validate_structure().errors
    ]
    assert ("unreachable_node", "nodes[detached_a]") in public_by_code_path
    assert ("unreachable_node", "nodes[detached_b]") in public_by_code_path
