from __future__ import annotations

from collections.abc import Callable

import pytest

from wf_core import END, Edge, ForeachNode, NodeDef, NodeUse, SchemaRef, Workflow
from wf_core.models.schemas import StateField, StateSchema
from wf_core.models.steps import (
    ConditionNode,
    InputPathBinding,
    InterruptNode,
    SubgraphNode,
)
from wf_core.validation.issues import ValidationIssueCode


def _foreach(node_id: str, *, over: str = "state.items", alias: str) -> ForeachNode:
    return ForeachNode.model_validate(
        {"id": node_id, "type": "foreach", "over": over, "as": alias}
    )


def _node_use(
    node_id: str, *, path: str | None = None, expression: dict | None = None
) -> NodeUse:
    if expression is not None:
        binding = {"target": "value", "expression": expression}
    elif path is not None:
        binding = {"target": "value", "path": path}
    else:
        binding = {"target": "value", "path": "state.items"}
    return NodeUse.model_validate(
        {"id": node_id, "type": "node", "node": "record", "input": [binding]}
    )


def _record_def() -> NodeDef:
    return NodeDef(
        name="record",
        input_schema=SchemaRef(type="object", properties={"value": {}}),
        output_schema=SchemaRef(type="object", properties={}),
        outcomes=["ok"],
    )


def _base_workflow(*, work_path: str = "context.foreach.orders.item") -> Workflow:
    return Workflow(
        name="validation_structured",
        input_schema=SchemaRef(type="object", properties={}),
        state_schema=StateSchema.from_field_map(
            {
                "items": StateField(type="array"),
                "orders_list": StateField(type="array"),
            }
        ),
        output_schema=SchemaRef(type="object", properties={}),
        node_defs=[_record_def()],
        start="customers",
        nodes=[
            _foreach("customers", over="state.items", alias="customer"),
            _foreach("orders", over="state.orders_list", alias="order"),
            _node_use("work", path=work_path),
            NodeUse.model_validate(
                {"id": "after_inner", "type": "node", "node": "record"}
            ),
        ],
        edges=[
            Edge.model_validate(
                {"from": "customers", "outcome": "loop", "to": "orders"}
            ),
            Edge.model_validate({"from": "orders", "outcome": "loop", "to": "work"}),
            Edge.model_validate({"from": "work", "outcome": "ok", "to": "orders"}),
            Edge.model_validate(
                {"from": "orders", "outcome": "done", "to": "after_inner"}
            ),
            Edge.model_validate(
                {"from": "after_inner", "outcome": "ok", "to": "customers"}
            ),
            Edge.model_validate({"from": "customers", "outcome": "done", "to": END}),
        ],
    )


def _issue(report, code: ValidationIssueCode, path: str):
    return next(
        (issue for issue in report.errors if issue.code == code and issue.path == path),
        None,
    )


def test_active_structured_foreach_item_path_is_valid() -> None:
    from wf_core.validation import validate_workflow

    workflow = _base_workflow(work_path="context.foreach.orders.item")
    report = validate_workflow(workflow)
    assert (
        _issue(
            report,
            ValidationIssueCode.INVALID_CONTEXT_PATH,
            "nodes[2].input[0].path",
        )
        is None
    )


def test_context_foreach_source_rejects_declared_scalar() -> None:
    """A readable context path is not iterable merely because it exists."""
    from wf_core.validation import validate_workflow

    workflow = _base_workflow()
    workflow.nodes[1] = _foreach(
        "orders",
        over="context.foreach.customers.index",
        alias="order",
    )

    report = validate_workflow(workflow)

    assert (
        _issue(
            report,
            ValidationIssueCode.INVALID_FOREACH_SOURCE,
            "nodes[1].over",
        )
        is not None
    )


def test_context_foreach_source_accepts_array_without_item_schema() -> None:
    """An array remains iterable when its element type is unconstrained."""
    from wf_core.validation import validate_workflow

    workflow = _base_workflow()
    workflow.state_schema = StateSchema.model_validate(
        {
            "type": "object",
            "properties": {
                "items": {"type": "array", "items": {"type": "array"}},
                "orders_list": {"type": "array"},
            },
        }
    )
    workflow.nodes[1] = _foreach(
        "orders",
        over="context.foreach.customers.item",
        alias="order",
    )

    report = validate_workflow(workflow)

    assert (
        _issue(
            report,
            ValidationIssueCode.INVALID_FOREACH_SOURCE,
            "nodes[1].over",
        )
        is None
    )


def test_nested_body_can_read_outer_and_inner_entries() -> None:
    from wf_core.validation import validate_workflow

    for path in (
        "context.foreach.customers.item",
        "context.foreach.orders.item",
        "context.foreach.customers.index",
        "context.foreach.orders.index",
    ):
        workflow = _base_workflow(work_path=path)
        report = validate_workflow(workflow)
        assert (
            _issue(
                report,
                ValidationIssueCode.INVALID_CONTEXT_PATH,
                "nodes[2].input[0].path",
            )
            is None
        ), path


def test_inactive_foreach_entry_is_rejected() -> None:
    from wf_core.validation import validate_workflow

    workflow = _base_workflow()
    workflow.nodes[3] = _node_use("after_inner", path="context.foreach.orders.item")
    report = validate_workflow(workflow)
    issue = _issue(
        report, ValidationIssueCode.INVALID_CONTEXT_PATH, "nodes[3].input[0].path"
    )
    assert issue is not None
    assert "context.foreach.orders.item" in issue.message
    assert "after_inner" in issue.message


def test_missing_foreach_id_is_rejected() -> None:
    from wf_core.validation import validate_workflow

    workflow = _base_workflow(work_path="context.foreach.missing.item")
    report = validate_workflow(workflow)
    issue = _issue(
        report, ValidationIssueCode.INVALID_CONTEXT_PATH, "nodes[2].input[0].path"
    )
    assert issue is not None
    assert "context.foreach.missing.item" in issue.message
    assert "work" in issue.message


def test_unknown_foreach_entry_field_is_rejected() -> None:
    from wf_core.validation import validate_workflow

    workflow = _base_workflow(work_path="context.foreach.orders.bogus")
    report = validate_workflow(workflow)
    issue = _issue(
        report, ValidationIssueCode.INVALID_CONTEXT_PATH, "nodes[2].input[0].path"
    )
    assert issue is not None


def test_unreachable_node_does_not_receive_root_context_fallback() -> None:
    from wf_core.validation import validate_workflow

    workflow = _base_workflow()
    workflow.nodes.append(_node_use("ghost", path="context.foreach.orders.item"))
    report = validate_workflow(workflow)
    issue = _issue(
        report, ValidationIssueCode.INVALID_CONTEXT_PATH, "nodes[4].input[0].path"
    )
    assert issue is not None


def test_workflow_output_cannot_read_completed_foreach_entry() -> None:
    from wf_core.models.steps import InputPathBinding
    from wf_core.validation import validate_workflow

    workflow = _base_workflow()
    workflow.output = [
        InputPathBinding.model_validate(
            {"target": "result", "path": "context.foreach.orders.item"}
        )
    ]
    report = validate_workflow(workflow)
    issue = _issue(report, ValidationIssueCode.INVALID_CONTEXT_PATH, "output[0].path")
    assert issue is not None


@pytest.mark.parametrize(
    ("make_node", "expected_path"),
    [
        (
            lambda: _node_use("work", path="context.foreach.missing.item"),
            "nodes[2].input[0].path",
        ),
        (
            lambda: _node_use(
                "work",
                expression={"kind": "path", "path": "context.foreach.missing.item"},
            ),
            "nodes[2].input[0].expression.path",
        ),
        (
            lambda: _node_use(
                "work",
                expression={
                    "kind": "array",
                    "items": [{"kind": "path", "path": "context.foreach.missing.item"}],
                },
            ),
            "nodes[2].input[0].expression.items[0].path",
        ),
    ],
)
def test_node_input_surfaces_report_exact_model_paths(make_node, expected_path) -> None:
    from wf_core.validation import validate_workflow

    workflow = _base_workflow()
    workflow.nodes[2] = make_node()
    report = validate_workflow(workflow)
    assert (
        _issue(report, ValidationIssueCode.INVALID_CONTEXT_PATH, expected_path)
        is not None
    )


def _missing_foreach_subgraph(workflow: Workflow, bad: str) -> str:
    workflow.nodes[2] = SubgraphNode.model_validate(
        {
            "id": "work",
            "type": "subgraph",
            "workflow": {"name": "child"},
            "input": [{"target": "order", "path": bad}],
        }
    )
    return "nodes[2].input[0].path"


def _missing_foreach_condition(workflow: Workflow, bad: str) -> str:
    workflow.nodes[2] = ConditionNode.model_validate(
        {"id": "work", "type": "condition", "check": {"op": "exists", "path": bad}}
    )
    workflow.edges = [
        Edge.model_validate({"from": "customers", "outcome": "loop", "to": "orders"}),
        Edge.model_validate({"from": "orders", "outcome": "loop", "to": "work"}),
        Edge.model_validate({"from": "work", "outcome": "true", "to": "orders"}),
        Edge.model_validate({"from": "work", "outcome": "false", "to": "orders"}),
        Edge.model_validate({"from": "orders", "outcome": "done", "to": "after_inner"}),
        Edge.model_validate(
            {"from": "after_inner", "outcome": "ok", "to": "customers"}
        ),
        Edge.model_validate({"from": "customers", "outcome": "done", "to": END}),
    ]
    return "nodes[2].check.path"


def _missing_foreach_over(workflow: Workflow, bad: str) -> str:
    workflow.nodes[1] = ForeachNode.model_validate(
        {"id": "orders", "type": "foreach", "over": bad, "as": "order"}
    )
    return "nodes[1].over"


def _missing_foreach_interrupt(workflow: Workflow, bad: str) -> str:
    workflow.nodes[2] = InterruptNode.model_validate(
        {
            "id": "work",
            "type": "interrupt",
            "kind": "approval",
            "request": [{"target": "order", "path": bad}],
        }
    )
    workflow.edges = [
        Edge.model_validate({"from": "customers", "outcome": "loop", "to": "orders"}),
        Edge.model_validate({"from": "orders", "outcome": "loop", "to": "work"}),
        Edge.model_validate({"from": "work", "outcome": "submitted", "to": "orders"}),
        Edge.model_validate({"from": "orders", "outcome": "done", "to": "after_inner"}),
        Edge.model_validate(
            {"from": "after_inner", "outcome": "ok", "to": "customers"}
        ),
        Edge.model_validate({"from": "customers", "outcome": "done", "to": END}),
    ]
    return "nodes[2].request[0].path"


def _missing_foreach_output(workflow: Workflow, bad: str) -> str:
    workflow.output = [
        InputPathBinding.model_validate({"target": "result", "path": bad})
    ]
    return "output[0].path"


@pytest.mark.parametrize(
    "configure_surface",
    [
        _missing_foreach_subgraph,
        _missing_foreach_condition,
        _missing_foreach_over,
        _missing_foreach_interrupt,
        _missing_foreach_output,
    ],
    ids=["subgraph", "condition", "foreach", "interrupt", "workflow-output"],
)
def test_all_model_surfaces_reject_missing_foreach_id(
    configure_surface: Callable[[Workflow, str], str],
) -> None:
    from wf_core.validation import validate_workflow

    workflow = _base_workflow()
    expected_path = configure_surface(workflow, "context.foreach.missing.item")
    report = validate_workflow(workflow)
    assert (
        _issue(report, ValidationIssueCode.INVALID_CONTEXT_PATH, expected_path)
        is not None
    )


def test_foreach_alias_cannot_use_reserved_context_name() -> None:
    from wf_core.validation import validate_workflow

    workflow = _base_workflow()
    workflow.nodes[1] = _foreach("orders", over="state.orders_list", alias="loop_item")
    report = validate_workflow(workflow)
    issue = next(
        (
            issue
            for issue in report.errors
            if issue.code == ValidationIssueCode.FOREACH_CONTEXT_ALIAS_CONFLICT
        ),
        None,
    )
    assert issue is not None
    assert issue.path == "nodes[1].as"


def test_nested_active_foreach_aliases_must_be_unique() -> None:
    from wf_core.validation import validate_workflow

    workflow = _base_workflow()
    workflow.nodes[0] = _foreach("customers", over="state.items", alias="same")
    workflow.nodes[1] = _foreach("orders", over="state.orders_list", alias="same")
    report = validate_workflow(workflow)
    issue = next(
        (
            issue
            for issue in report.errors
            if issue.code == ValidationIssueCode.FOREACH_CONTEXT_ALIAS_CONFLICT
        ),
        None,
    )
    assert issue is not None
    assert issue.path == "nodes[1].as"


def test_sibling_foreach_aliases_may_match_when_never_active_together() -> None:
    from wf_core.validation import validate_workflow

    workflow = Workflow(
        name="siblings",
        input_schema=SchemaRef(type="object", properties={}),
        state_schema=StateSchema.from_field_map(
            {
                "items": StateField(type="array"),
                "other": StateField(type="array"),
            }
        ),
        output_schema=SchemaRef(type="object", properties={}),
        node_defs=[_record_def()],
        start="start",
        nodes=[
            NodeUse(id="start", type="node", node="record"),
            _foreach("left", over="state.items", alias="same"),
            _foreach("right", over="state.other", alias="same"),
            NodeUse(id="left_body", type="node", node="record"),
            NodeUse(id="right_body", type="node", node="record"),
            NodeUse(id="join", type="node", node="record"),
        ],
        edges=[
            Edge.model_validate({"from": "start", "outcome": "ok", "to": "left"}),
            Edge.model_validate({"from": "left", "outcome": "loop", "to": "left_body"}),
            Edge.model_validate({"from": "left_body", "outcome": "ok", "to": "left"}),
            Edge.model_validate({"from": "left", "outcome": "done", "to": "right"}),
            Edge.model_validate(
                {"from": "right", "outcome": "loop", "to": "right_body"}
            ),
            Edge.model_validate({"from": "right_body", "outcome": "ok", "to": "right"}),
            Edge.model_validate({"from": "right", "outcome": "done", "to": "join"}),
            Edge.model_validate({"from": "join", "outcome": "ok", "to": END}),
        ],
    )
    report = validate_workflow(workflow)
    assert not [
        issue
        for issue in report.errors
        if issue.code == ValidationIssueCode.FOREACH_CONTEXT_ALIAS_CONFLICT
    ]


def test_child_workflow_cannot_address_caller_foreach_context() -> None:
    """A child scope must receive caller values through declared input.

    The child is validated alone, so a path naming the caller's foreach id
    is a missing id in the child scope and fails closed.
    """
    from wf_core.validation import validate_workflow

    child = Workflow(
        name="child",
        input_schema=SchemaRef(type="object", properties={"order": {}}),
        state_schema=StateSchema.from_field_map({}),
        output_schema=SchemaRef(type="object", properties={}),
        node_defs=[_record_def()],
        start="work",
        nodes=[_node_use("work", path="context.foreach.orders.item")],
        edges=[Edge.model_validate({"from": "work", "outcome": "ok", "to": END})],
    )
    report = validate_workflow(child)
    issue = _issue(
        report, ValidationIssueCode.INVALID_CONTEXT_PATH, "nodes[0].input[0].path"
    )
    assert issue is not None
    assert "context.foreach.orders.item" in issue.message


def test_object_expression_and_nested_conditions_report_exact_paths() -> None:
    from wf_core.models.steps import ConditionNode, InterruptNode
    from wf_core.validation import validate_workflow

    bad = "context.foreach.missing.item"
    workflow = _base_workflow()
    workflow.nodes[2] = _node_use(
        "work",
        expression={
            "kind": "object",
            "fields": {"order": {"kind": "path", "path": bad}},
        },
    )
    report = validate_workflow(workflow)
    assert (
        _issue(
            report,
            ValidationIssueCode.INVALID_CONTEXT_PATH,
            "nodes[2].input[0].expression.fields.order.path",
        )
        is not None
    )

    workflow = _base_workflow()
    workflow.nodes[2] = ConditionNode.model_validate(
        {
            "id": "work",
            "type": "condition",
            "check": {
                "op": "not",
                "arg": {
                    "op": "and",
                    "args": [
                        {"op": "exists", "path": bad},
                        {
                            "op": "eq",
                            "left": {"path": bad},
                            "right": {"value": 1},
                        },
                    ],
                },
            },
        }
    )
    workflow.edges = [
        Edge.model_validate({"from": "customers", "outcome": "loop", "to": "orders"}),
        Edge.model_validate({"from": "orders", "outcome": "loop", "to": "work"}),
        Edge.model_validate({"from": "work", "outcome": "true", "to": "orders"}),
        Edge.model_validate({"from": "work", "outcome": "false", "to": "orders"}),
        Edge.model_validate({"from": "orders", "outcome": "done", "to": "after_inner"}),
        Edge.model_validate(
            {"from": "after_inner", "outcome": "ok", "to": "customers"}
        ),
        Edge.model_validate({"from": "customers", "outcome": "done", "to": END}),
    ]
    report = validate_workflow(workflow)
    assert (
        _issue(
            report,
            ValidationIssueCode.INVALID_CONTEXT_PATH,
            "nodes[2].check.arg.args[0].path",
        )
        is not None
    )
    assert (
        _issue(
            report,
            ValidationIssueCode.INVALID_CONTEXT_PATH,
            "nodes[2].check.arg.args[1].left.path",
        )
        is not None
    )

    workflow = _base_workflow()
    workflow.nodes[2] = InterruptNode.model_validate(
        {
            "id": "work",
            "type": "interrupt",
            "kind": "approval",
            "request": [
                {
                    "target": "order",
                    "expression": {"kind": "path", "path": bad},
                }
            ],
        }
    )
    workflow.edges = [
        Edge.model_validate({"from": "customers", "outcome": "loop", "to": "orders"}),
        Edge.model_validate({"from": "orders", "outcome": "loop", "to": "work"}),
        Edge.model_validate({"from": "work", "outcome": "submitted", "to": "orders"}),
        Edge.model_validate({"from": "orders", "outcome": "done", "to": "after_inner"}),
        Edge.model_validate(
            {"from": "after_inner", "outcome": "ok", "to": "customers"}
        ),
        Edge.model_validate({"from": "customers", "outcome": "done", "to": END}),
    ]
    report = validate_workflow(workflow)
    assert (
        _issue(
            report,
            ValidationIssueCode.INVALID_CONTEXT_PATH,
            "nodes[2].request[0].expression.path",
        )
        is not None
    )


def _nested_ref_workflow(*, work_path: str) -> Workflow:
    workflow = _base_workflow(work_path=work_path)
    workflow.state_schema = StateSchema.model_validate(
        {
            "type": "object",
            "properties": {
                "items": {"type": "array", "items": {"type": "string"}},
                "orders_list": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/Order"},
                },
            },
            "$defs": {
                "Order": {
                    "type": "object",
                    "properties": {
                        "sku": {"type": "string"},
                        "detail": {"$ref": "#/$defs/Detail"},
                    },
                    "required": ["sku", "detail"],
                },
                "Detail": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                },
            },
        }
    )
    return workflow


def test_nested_ref_item_subpath_is_accepted() -> None:
    from wf_core.validation import validate_workflow

    workflow = _nested_ref_workflow(work_path="context.foreach.orders.item.detail.name")
    report = validate_workflow(workflow)
    assert [
        issue
        for issue in report.errors
        if issue.code == ValidationIssueCode.INVALID_CONTEXT_PATH
    ] == []


def test_nested_ref_item_unknown_leaf_reports_available_keys() -> None:
    from wf_core.validation import validate_workflow

    workflow = _nested_ref_workflow(
        work_path="context.foreach.orders.item.detail.bogus"
    )
    report = validate_workflow(workflow)
    issue = _issue(
        report, ValidationIssueCode.INVALID_CONTEXT_PATH, "nodes[2].input[0].path"
    )
    assert issue is not None
    assert "'bogus'" in issue.message
    assert "available: name" in issue.message


def _composer_ref_workflow(*, work_path: str) -> Workflow:
    """State schema with anyOf-optional, sibling-extended, recursive shapes."""
    workflow = _base_workflow(work_path=work_path)
    workflow.state_schema = StateSchema.model_validate(
        {
            "type": "object",
            "properties": {
                "items": {"type": "array", "items": {"type": "string"}},
                "orders_list": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/Order"},
                },
            },
            "$defs": {
                "Order": {
                    "type": "object",
                    "properties": {
                        "sku": {"type": "string"},
                        "detail": {
                            "anyOf": [
                                {"$ref": "#/$defs/Detail"},
                                {"type": "null"},
                            ]
                        },
                        "nick": {
                            "$ref": "#/$defs/Detail",
                            "description": "Short display name",
                            "properties": {"label": {"type": "string"}},
                        },
                    },
                    "required": ["sku"],
                },
                "Detail": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                },
            },
        }
    )
    return workflow


def test_optional_nested_model_subpath_is_accepted() -> None:
    from wf_core.validation import validate_workflow

    workflow = _composer_ref_workflow(
        work_path="context.foreach.orders.item.detail.name"
    )
    report = validate_workflow(workflow)
    assert [
        issue
        for issue in report.errors
        if issue.code == ValidationIssueCode.INVALID_CONTEXT_PATH
    ] == []


def test_ref_sibling_properties_extend_the_target() -> None:
    from wf_core.validation import validate_workflow

    for work_path in (
        "context.foreach.orders.item.nick.name",
        "context.foreach.orders.item.nick.label",
    ):
        workflow = _composer_ref_workflow(work_path=work_path)
        report = validate_workflow(workflow)
        assert [
            issue
            for issue in report.errors
            if issue.code == ValidationIssueCode.INVALID_CONTEXT_PATH
        ] == []


def _recursive_ref_workflow(*, work_path: str) -> Workflow:
    workflow = _base_workflow(work_path=work_path)
    workflow.state_schema = StateSchema.model_validate(
        {
            "type": "object",
            "properties": {
                "items": {"type": "array", "items": {"type": "string"}},
                "orders_list": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/Category"},
                },
            },
            "$defs": {
                "Category": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "parent": {
                            "anyOf": [
                                {"$ref": "#/$defs/Category"},
                                {"type": "null"},
                            ]
                        },
                        "children": {
                            "type": "array",
                            "items": {"$ref": "#/$defs/Category"},
                        },
                    },
                    "required": ["name"],
                },
            },
        }
    )
    return workflow


def test_recursive_ref_paths_validate_through_definitions() -> None:
    from wf_core.validation import validate_workflow

    for work_path in (
        "context.foreach.orders.item.parent.name",
        "context.foreach.orders.item.children",
    ):
        workflow = _recursive_ref_workflow(work_path=work_path)
        report = validate_workflow(workflow)
        assert [
            issue
            for issue in report.errors
            if issue.code == ValidationIssueCode.INVALID_CONTEXT_PATH
        ] == []


def test_recursive_ref_unknown_leaf_reports_defined_keys() -> None:
    from wf_core.validation import validate_workflow

    workflow = _recursive_ref_workflow(
        work_path="context.foreach.orders.item.parent.bogus"
    )
    report = validate_workflow(workflow)
    issue = _issue(
        report, ValidationIssueCode.INVALID_CONTEXT_PATH, "nodes[2].input[0].path"
    )
    assert issue is not None
    assert "'bogus'" in issue.message
    assert "available: children,name,parent" in issue.message
