from __future__ import annotations

import pytest

from wf_core import (
    END,
    Edge,
    EndNode,
    InputExpressionBinding,
    InputPathBinding,
    NodeDef,
    NodeUse,
    PreparedSubgraph,
    RuntimeContext,
    SchemaRef,
    StateField,
    StateSchema,
    SubgraphNode,
    Workflow,
    WorkflowExecutionError,
    execute_workflow,
    resume_workflow,
)
from wf_core.models.steps import InterruptNode
from wf_core.runtime.input_bindings import (
    resolve_input_expression,
    resolve_step_input_bindings,
)

COMPOSITE_BINDING = {
    "target": "request",
    "expression": {
        "kind": "object",
        "fields": {
            "items": {
                "kind": "array",
                "items": [
                    {"kind": "path", "path": "state.foo"},
                    {"kind": "literal", "value": "wowcool"},
                ],
            },
            "separator": {"kind": "literal", "value": " "},
        },
    },
}


def test_resolver_builds_nested_json_with_input_state_and_context_paths() -> None:
    expression = InputExpressionBinding.model_validate(
        {
            "target": "request",
            "expression": {
                "kind": "object",
                "fields": {
                    "state_value": {"kind": "path", "path": "state.foo"},
                    "input_value": {"kind": "path", "path": "input.prefix"},
                    "context_value": {
                        "kind": "path",
                        "path": "context.prior_outcome",
                    },
                },
            },
        }
    ).expression
    resolved = resolve_input_expression(
        expression,
        state={"foo": "hello"},
        workflow_input={"prefix": "say"},
        context={"prior_outcome": "ok"},
        label="node 'concat' input",
        location="request",
    )

    assert resolved == {
        "state_value": "hello",
        "input_value": "say",
        "context_value": "ok",
    }


def test_resolver_preserves_explicit_null_and_binding_order() -> None:
    bindings = [
        InputExpressionBinding.model_validate(
            {
                "target": "request.first",
                "expression": {"kind": "literal", "value": None},
            }
        ),
        InputExpressionBinding.model_validate(
            {
                "target": "request.second",
                "expression": {"kind": "path", "path": "input.value"},
            }
        ),
    ]

    assert resolve_step_input_bindings(
        bindings,
        state={},
        workflow_input={"value": "second"},
        context={},
        label="node 'ordered' input",
    ) == {"request": {"first": None, "second": "second"}}


def test_simple_path_binding_preserves_legacy_value_identity() -> None:
    legacy_value = {"opaque": object()}

    resolved = resolve_step_input_bindings(
        [InputPathBinding(target="request.value", path="state.value")],
        state={"value": legacy_value},
        workflow_input={},
        context={},
        label="node 'legacy' input",
    )

    assert resolved["request"]["value"] is legacy_value


def test_composite_path_expression_keeps_strict_json_contract() -> None:
    legacy_value = {"opaque": object()}
    binding = InputExpressionBinding.model_validate(
        {
            "target": "request.value",
            "expression": {"kind": "path", "path": "state.value"},
        }
    )

    with pytest.raises(WorkflowExecutionError, match="node 'composite' input"):
        resolve_step_input_bindings(
            [binding],
            state={"value": legacy_value},
            workflow_input={},
            context={},
            label="node 'composite' input",
        )


def test_resolver_reports_nested_missing_path_location() -> None:
    expression = InputExpressionBinding.model_validate(
        {
            "target": "request",
            "expression": {
                "kind": "object",
                "fields": {
                    "items": {
                        "kind": "array",
                        "items": [
                            {"kind": "path", "path": "state.missing"},
                        ],
                    }
                },
            },
        }
    ).expression

    with pytest.raises(
        WorkflowExecutionError,
        match=r"node 'concat' input request\.items\[0\]",
    ):
        resolve_input_expression(
            expression,
            state={},
            workflow_input={},
            context={},
            label="node 'concat' input",
            location="request",
        )


def test_resolver_reports_local_target_location() -> None:
    bindings = [
        InputExpressionBinding.model_validate(
            {
                "target": "request",
                "expression": {
                    "kind": "literal",
                    "value": "first",
                },
            }
        ),
        InputExpressionBinding.model_validate(
            {
                "target": "request.title",
                "expression": {"kind": "literal", "value": "second"},
            }
        ),
    ]

    with pytest.raises(
        WorkflowExecutionError,
        match=r"node 'concat' input request\.title",
    ):
        resolve_step_input_bindings(
            bindings,
            state={},
            workflow_input={},
            context={},
            label="node 'concat' input",
        )


def test_normal_node_execution_resolves_composite_input() -> None:
    seen: dict[str, object] = {}

    def concat(
        payload: dict[str, object], _context: RuntimeContext
    ) -> dict[str, object]:
        seen.update(payload)
        return {"outcome": "ok", "output": {}}

    workflow = _node_workflow(
        input_bindings=[COMPOSITE_BINDING],
        state_fields={"foo": StateField(type="string", default="hello")},
    )
    run = execute_workflow(workflow, {}, {"concat": concat})

    assert run.status.value == "completed"
    assert seen == {"request": {"items": ["hello", "wowcool"], "separator": " "}}


def test_prepared_subgraph_input_resolves_composite_input() -> None:
    parent = _parent_subgraph_workflow([COMPOSITE_BINDING])
    child = Workflow(
        name="child",
        input_schema=_schema({"request": {"type": "object"}}),
        state_schema=StateSchema.from_field_map({}),
        output_schema=_schema({}),
        outcomes=["ok"],
        start="done",
        nodes=[EndNode(id="done", type="end", outcome="ok")],
        edges=[],
    )

    run = execute_workflow(
        parent,
        {},
        {},
        subgraphs={"child": PreparedSubgraph(workflow=child, registry={})},
    )

    child_scope = next(
        scope for scope in run.scopes.values() if scope.workflow_name == "child"
    )
    assert child_scope.workflow_input == {
        "request": {"items": ["hello", "wowcool"], "separator": " "}
    }


def test_interrupt_request_resolves_composite_input_and_resume_continues() -> None:
    workflow = Workflow(
        name="interrupt_expression",
        input_schema=_schema({}),
        state_schema=StateSchema.from_field_map(
            {"foo": StateField(type="string", default="hello")}
        ),
        output_schema=_schema({}),
        outcomes=["submitted"],
        start="review",
        nodes=[
            InterruptNode.model_validate(
                {
                    "id": "review",
                    "type": "interrupt",
                    "kind": "review",
                    "request": [COMPOSITE_BINDING],
                    "resume": [],
                }
            ),
            EndNode(id="done", type="end", outcome="submitted"),
        ],
        edges=[
            Edge.model_validate(
                {"from": "review", "outcome": "submitted", "to": "done"}
            )
        ],
    )

    run = execute_workflow(workflow, {}, {})

    assert run.interrupt is not None
    assert run.interrupt.payload == {
        "request": {"items": ["hello", "wowcool"], "separator": " "}
    }
    assert (
        resume_workflow(workflow, run, {}, resume_payload={}).status.value
        == "completed"
    )


def _node_workflow(
    *,
    input_bindings: list[dict[str, object]],
    state_fields: dict[str, StateField],
) -> Workflow:
    return Workflow(
        name="node_expression",
        input_schema=_schema({}),
        state_schema=StateSchema.from_field_map(state_fields),
        output_schema=_schema({}),
        outcomes=["ok"],
        start="concat",
        node_defs=[
            NodeDef(
                name="concat",
                input_schema=_schema({"request": {"type": "object"}}),
                output_schema=_schema({}),
                outcomes=["ok"],
            )
        ],
        nodes=[
            NodeUse(
                id="concat",
                type="node",
                node="concat",
                input=input_bindings,
            )
        ],
        edges=[Edge.model_validate({"from": "concat", "outcome": "ok", "to": END})],
    )


def _parent_subgraph_workflow(input_bindings: list[dict[str, object]]) -> Workflow:
    return Workflow(
        name="parent",
        input_schema=_schema({}),
        state_schema=StateSchema.from_field_map(
            {"foo": StateField(type="string", default="hello")}
        ),
        output_schema=_schema({}),
        outcomes=["ok"],
        start="child",
        nodes=[
            SubgraphNode(
                id="child",
                type="subgraph",
                workflow="child",
                input_schema=_schema({"request": {"type": "object"}}),
                output_schema=_schema({}),
                input=input_bindings,
            )
        ],
        edges=[Edge.model_validate({"from": "child", "outcome": "ok", "to": END})],
    )


def _schema(properties: dict[str, object]) -> SchemaRef:
    return SchemaRef.model_validate({"type": "object", "properties": properties})
