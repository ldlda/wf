from __future__ import annotations

import pytest
from jsonschema import Draft202012Validator

from wf_core import END, Edge, ForeachNode, NodeUse, SchemaRef, StateSchema, Workflow
from wf_core.analysis.context_scopes import (
    ContextFieldAvailability,
    context_analysis_warnings,
    context_fields_by_node,
)
from wf_core.context_contracts import STANDARD_CONTEXT_FIELDS, foreach_context_fields
from wf_core.errors import WorkflowExecutionError
from wf_core.models.steps import Step
from wf_core.run_state import ExecutionFrame, RunState, RunStatus
from wf_core.runtime.ops.frames import frame_context_view


def _node(node_id: str) -> NodeUse:
    return NodeUse(id=node_id, type="node", node="noop")


def _foreach(
    node_id: str,
    *,
    alias: str,
    mode: str = "serial",
    over: str = "state.items",
) -> ForeachNode:
    data: dict[str, object] = {
        "id": node_id,
        "type": "foreach",
        "over": over,
        "as": alias,
        "mode": mode,
    }
    if mode == "concurrent":
        data["concurrent"] = {"max_active": 2, "max_outstanding": 2}
    return ForeachNode.model_validate(data)


def _workflow(
    *,
    start: str,
    nodes: list[Step],
    edges: list[dict[str, str]],
    state_schema: dict[str, object] | None = None,
) -> Workflow:
    return Workflow(
        name="context-analysis",
        input_schema=SchemaRef(type="object"),
        state_schema=StateSchema.model_validate(
            state_schema
            or {
                "type": "object",
                "properties": {"items": {"type": "array", "items": {"type": "string"}}},
            }
        ),
        output_schema=SchemaRef(type="object"),
        start=start,
        nodes=nodes,
        edges=[Edge.model_validate(edge) for edge in edges],
    )


def _field_map(workflow: Workflow, node_id: str) -> dict[str, ContextFieldAvailability]:
    return {
        field.contract.name: field
        for field in context_fields_by_node(workflow)[node_id]
    }


def _run_with(*frames: ExecutionFrame) -> RunState:
    run = RunState(
        workflow_name="demo",
        status=RunStatus.RUNNING,
        workflow_input={},
        state={},
    )
    for frame in frames:
        run.frames[frame.id] = frame
    return run


def test_frame_context_view_uses_standard_and_foreach_contract_keys() -> None:
    root = ExecutionFrame(
        id="root",
        kind="root",
        node_id="plain",
        prior_outcome="ok",
        activated_incoming_edge="start",
    )
    ordinary = frame_context_view(_run_with(root), root).graph
    assert ordinary["prior_outcome"] == "ok"
    assert ordinary["activated_incoming_edge"] == "start"
    assert ordinary["scope_id"] == "root"
    assert ordinary["lineage_id"] == "root"
    assert ordinary["parent_lineage_id"] is None
    assert ordinary["foreach"] == {}
    assert "loop_item" not in ordinary

    iteration = ExecutionFrame(
        id="root:each:0",
        kind="foreach_iteration",
        node_id="body",
        metadata={
            "foreach_node_id": "each",
            "activation_id": "act-1",
            "loop_item": "a",
            "loop_index": 0,
            "loop_alias": "item",
        },
    )
    context = frame_context_view(_run_with(iteration), iteration).graph
    assert context["loop_item"] == "a"
    assert context["loop_index"] == 0
    assert context["item"] == "a"


def test_context_contracts_deduplicate_aliases_that_are_standard_loop_keys() -> None:
    assert STANDARD_CONTEXT_FIELDS[0].schema == {"type": ["string", "null"]}
    assert [field.name for field in foreach_context_fields("loop_item", {})] == [
        "loop_item",
        "loop_index",
    ]


def test_all_standard_context_names_are_reserved_from_foreach_aliases() -> None:
    standard_names = {field.name for field in STANDARD_CONTEXT_FIELDS}

    for name in standard_names:
        foreach_names = {
            field.name for field in foreach_context_fields(name, {"type": "string"})
        }
        assert name not in foreach_names
        # A reserved alias can never back a runtime entry: the derived view
        # fails closed instead of silently shadowing the standard key.
        frame = ExecutionFrame(
            id="child",
            kind="foreach_iteration",
            node_id="body",
            scope_id="scope",
            lineage_id="lineage",
            parent_lineage_id="parent",
            prior_outcome="ok",
            activated_incoming_edge="start",
            metadata={
                "foreach_node_id": "each",
                "activation_id": "act-1",
                "loop_item": "item",
                "loop_index": 0,
                "loop_alias": name,
            },
        )
        with pytest.raises(WorkflowExecutionError, match="reserved context keys"):
            frame_context_view(_run_with(frame), frame)


def test_serial_and_concurrent_foreach_expose_the_same_scoped_context() -> None:
    for mode in ("serial", "concurrent"):
        workflow = _workflow(
            start="each",
            nodes=[
                _foreach("each", alias="item", mode=mode),
                _node("body"),
                _node("tail"),
            ],
            edges=[
                {"from": "each", "outcome": "loop", "to": "body"},
                {"from": "each", "outcome": "done", "to": "tail"},
                {"from": "body", "outcome": "ok", "to": "each"},
                {"from": "tail", "outcome": "ok", "to": END},
            ],
        )

        body = _field_map(workflow, "body")
        assert body["loop_item"].availability == "available"
        assert body["loop_index"].availability == "available"
        assert body["item"].availability == "available"
        assert "item" not in _field_map(workflow, "tail")


def test_foreach_item_schema_and_configured_alias_are_reported() -> None:
    workflow = _workflow(
        start="each",
        nodes=[_foreach("each", alias="record"), _node("body")],
        edges=[
            {"from": "each", "outcome": "loop", "to": "body"},
            {"from": "body", "outcome": "ok", "to": "each"},
            {"from": "each", "outcome": "done", "to": END},
        ],
    )

    fields = _field_map(workflow, "body")
    assert fields["record"].contract.schema == {"type": "string"}
    assert fields["loop_item"].contract.schema == {"type": "string"}
    assert fields["loop_index"].contract.schema == {"type": "integer"}


def test_foreach_item_schema_resolves_bounded_local_array_reference() -> None:
    workflow = _workflow(
        start="each",
        nodes=[_foreach("each", alias="record"), _node("body")],
        edges=[
            {"from": "each", "outcome": "loop", "to": "body"},
            {"from": "body", "outcome": "ok", "to": "each"},
            {"from": "each", "outcome": "done", "to": END},
        ],
        state_schema={
            "type": "object",
            "properties": {"items": {"$ref": "#/$defs/Items"}},
            "$defs": {
                "Items": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/Item"},
                },
                "Item": {
                    "type": "object",
                    "properties": {"id": {"type": "string"}},
                    "required": ["id"],
                },
            },
        },
    )

    fields = _field_map(workflow, "body")
    assert fields["loop_item"].contract.schema["type"] == "object"
    assert fields["loop_item"].contract.schema["properties"] == {
        "id": {"type": "string"}
    }
    assert fields["record"].contract.schema["properties"] == {"id": {"type": "string"}}


def test_region_conflicted_node_receives_no_guaranteed_foreach_fields() -> None:
    workflow = _workflow(
        start="start",
        nodes=[_node("start"), _foreach("each", alias="item"), _node("body")],
        edges=[
            {"from": "start", "outcome": "ok", "to": "body"},
            {"from": "start", "outcome": "loop", "to": "each"},
            {"from": "each", "outcome": "loop", "to": "body"},
            {"from": "each", "outcome": "done", "to": END},
            {"from": "body", "outcome": "ok", "to": "each"},
        ],
    )

    fields = context_fields_by_node(workflow)
    assert "body" not in fields or "item" not in {
        field.contract.name for field in fields.get("body", ())
    }
    warnings = context_analysis_warnings(workflow)
    assert any(
        "control region" in warning or "conflict" in warning for warning in warnings
    )


def test_nested_foreach_replaces_inner_scope_and_restores_outer_scope() -> None:
    workflow = _workflow(
        start="outer",
        nodes=[
            _foreach("outer", alias="outer_item"),
            _foreach("inner", alias="inner_item", over="state.inner_items"),
            _node("inner_body"),
            _node("after_inner"),
        ],
        edges=[
            {"from": "outer", "outcome": "loop", "to": "inner"},
            {"from": "inner", "outcome": "loop", "to": "inner_body"},
            {"from": "inner", "outcome": "done", "to": "after_inner"},
            {"from": "inner_body", "outcome": "ok", "to": "inner"},
            {"from": "after_inner", "outcome": "ok", "to": "outer"},
            {"from": "outer", "outcome": "done", "to": END},
        ],
        state_schema={
            "type": "object",
            "properties": {
                "items": {"type": "array", "items": {"type": "string"}},
                "inner_items": {"type": "array", "items": {"type": "integer"}},
            },
        },
    )

    inner = _field_map(workflow, "inner_body")
    after_inner = _field_map(workflow, "after_inner")
    outer_item_schema = {"type": "string"}
    inner_item_schema = {"type": "integer"}

    assert inner["outer_item"].schema == outer_item_schema
    assert inner["inner_item"].schema == inner_item_schema
    assert inner["loop_item"].schema == inner_item_schema
    foreach_schema = inner["foreach"].schema
    assert set(foreach_schema["properties"]) == {"outer", "inner"}
    assert foreach_schema["properties"]["outer"]["properties"]["item"] == (
        outer_item_schema
    )
    assert foreach_schema["properties"]["inner"]["properties"]["index"] == {
        "type": "integer"
    }
    assert after_inner["outer_item"].availability == "available"
    assert "inner_item" not in after_inner


def test_inner_completion_schema_restores_outer_structured_entry() -> None:
    workflow = _workflow(
        start="outer",
        nodes=[
            _foreach("outer", alias="outer_item"),
            _foreach("inner", alias="inner_item", over="state.inner_items"),
            _node("inner_body"),
            _node("after_inner"),
        ],
        edges=[
            {"from": "outer", "outcome": "loop", "to": "inner"},
            {"from": "inner", "outcome": "loop", "to": "inner_body"},
            {"from": "inner", "outcome": "done", "to": "after_inner"},
            {"from": "inner_body", "outcome": "ok", "to": "inner"},
            {"from": "after_inner", "outcome": "ok", "to": "outer"},
            {"from": "outer", "outcome": "done", "to": END},
        ],
        state_schema={
            "type": "object",
            "properties": {
                "items": {"type": "array", "items": {"type": "string"}},
                "inner_items": {"type": "array", "items": {"type": "integer"}},
            },
        },
    )
    after_inner = _field_map(workflow, "after_inner")
    foreach_schema = after_inner["foreach"].schema
    assert set(foreach_schema["properties"]) == {"outer"}


def test_nested_foreach_preserves_context_backed_item_schema() -> None:
    workflow = _workflow(
        start="outer",
        nodes=[
            _foreach("outer", alias="outer_item"),
            _foreach("inner", alias="inner_item", over="context.outer_item"),
            _node("inner_body"),
            _node("after_inner"),
        ],
        edges=[
            {"from": "outer", "outcome": "loop", "to": "inner"},
            {"from": "inner", "outcome": "loop", "to": "inner_body"},
            {"from": "inner", "outcome": "done", "to": "after_inner"},
            {"from": "inner_body", "outcome": "ok", "to": "inner"},
            {"from": "after_inner", "outcome": "ok", "to": "outer"},
            {"from": "outer", "outcome": "done", "to": END},
        ],
        state_schema={
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"id": {"type": "string"}},
                            "required": ["id"],
                        },
                    },
                }
            },
        },
    )

    fields = _field_map(workflow, "inner_body")
    expected = {
        "type": "object",
        "properties": {"id": {"type": "string"}},
        "required": ["id"],
    }
    assert fields["loop_item"].contract.schema == expected
    assert fields["inner_item"].contract.schema == expected


def test_malformed_routes_warn_without_granting_a_scoped_alias() -> None:
    workflow = _workflow(
        start="each",
        nodes=[_foreach("each", alias="item"), _node("body")],
        edges=[
            {"from": "each", "outcome": "done", "to": "missing"},
            {"from": "each", "outcome": "ok", "to": "body"},
            {"from": "body", "outcome": "ok", "to": END},
        ],
    )

    assert "item" not in _field_map(workflow, "body")
    warnings = context_analysis_warnings(workflow)
    assert any("missing" in warning for warning in warnings)
    assert any("loop" in warning for warning in warnings)


def test_cyclic_graph_analysis_memoizes_node_and_frame_scope() -> None:
    workflow = _workflow(
        start="a",
        nodes=[_node("a"), _node("b")],
        edges=[
            {"from": "a", "outcome": "ok", "to": "b"},
            {"from": "b", "outcome": "ok", "to": "a"},
        ],
    )

    fields = context_fields_by_node(workflow)
    assert set(fields) == {"a", "b"}
    assert fields["a"]
    assert fields["b"]


def test_scoped_cycle_terminates_and_preserves_scoped_field_availability() -> None:
    workflow = _workflow(
        start="each",
        nodes=[_foreach("each", alias="item"), _node("body")],
        edges=[
            {"from": "each", "outcome": "loop", "to": "body"},
            {"from": "body", "outcome": "ok", "to": "each"},
            {"from": "each", "outcome": "done", "to": END},
        ],
    )

    fields = context_fields_by_node(workflow)
    assert fields["body"]
    assert _field_map(workflow, "body")["item"].availability == "available"
    # A canonical back-edge pops the item stack, so the controller itself
    # stays in the outer region and exposes no item alias.
    assert "item" not in _field_map(workflow, "each")


def _composer_state_schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
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
                    "nick": {
                        "$ref": "#/$defs/Detail",
                        "description": "Short display name",
                        "properties": {"label": {"type": "string"}},
                    },
                },
            },
            "Detail": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
            },
        },
    }


def _composer_workflow() -> Workflow:
    return _workflow(
        start="orders",
        nodes=[
            _foreach("orders", over="state.orders_list", alias="order"),
            _node("body"),
        ],
        edges=[
            {"from": "orders", "outcome": "loop", "to": "body"},
            {"from": "body", "outcome": "ok", "to": "orders"},
            {"from": "orders", "outcome": "done", "to": END},
        ],
        state_schema=_composer_state_schema(),
    )


def test_ref_sibling_metadata_and_properties_survive_projection() -> None:
    from wf_core.analysis.context_scopes import context_schema_for_node
    from wf_core.schema_navigation import SchemaNavigator

    schema = context_schema_for_node(_composer_workflow(), "body")
    item = schema["properties"]["foreach"]["properties"]["orders"]["properties"]["item"]
    assert set(item["properties"]) == {"sku", "nick"}
    nick = item["properties"]["nick"]
    assert nick["description"] == "Short display name"
    navigator = SchemaNavigator(item)
    assert navigator.first_unknown(("nick", "name")) == (None, "")
    assert navigator.first_unknown(("nick", "label")) == (None, "")


def test_recursive_item_schema_carries_definitions() -> None:
    from wf_core.analysis.context_scopes import context_schema_for_node

    workflow = _workflow(
        start="cats",
        nodes=[
            _foreach("cats", over="state.cats", alias="cat"),
            _node("body"),
        ],
        edges=[
            {"from": "cats", "outcome": "loop", "to": "body"},
            {"from": "body", "outcome": "ok", "to": "cats"},
            {"from": "cats", "outcome": "done", "to": END},
        ],
        state_schema={
            "type": "object",
            "properties": {
                "cats": {
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
                    },
                },
            },
        },
    )
    schema = context_schema_for_node(workflow, "body")
    item = schema["properties"]["foreach"]["properties"]["cats"]["properties"]["item"]
    # The detached item is a resource with the definitions its refs require.
    assert item["$defs"]["Category"]["properties"]["name"] == {"type": "string"}


@pytest.mark.parametrize(
    ("definitions_key", "reference_prefix"),
    [("$defs", "#/$defs/"), ("definitions", "#/definitions/")],
)
def test_recursive_context_schema_is_standalone(
    definitions_key: str, reference_prefix: str
) -> None:
    """Recursive item refs must resolve from the complete emitted schema."""
    from wf_core.analysis.context_scopes import context_schema_for_node

    workflow = _workflow(
        start="cats",
        nodes=[
            _foreach("cats", over="state.cats", alias="cat"),
            _node("body"),
        ],
        edges=[
            {"from": "cats", "outcome": "loop", "to": "body"},
            {"from": "body", "outcome": "ok", "to": "cats"},
            {"from": "cats", "outcome": "done", "to": END},
        ],
        state_schema={
            "type": "object",
            "properties": {
                "cats": {
                    "type": "array",
                    "items": {"$ref": reference_prefix + "Category"},
                },
            },
            definitions_key: {
                "Category": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "parent": {"$ref": reference_prefix + "Category"},
                    },
                    "required": ["name"],
                },
            },
        },
    )
    schema = context_schema_for_node(workflow, "body")
    item_value = {"name": "kitten", "parent": {"name": "cat"}}
    context_value = {
        "prior_outcome": None,
        "activated_incoming_edge": None,
        "scope_id": "root",
        "lineage_id": "item-lineage",
        "parent_lineage_id": "root",
        "foreach": {
            "cats": {
                "node_id": "cats",
                "activation_id": "activation",
                "frame_id": "item-frame",
                "scope_id": "root",
                "lineage_id": "item-lineage",
                "index": 0,
                "item": item_value,
            }
        },
        "loop_item": item_value,
        "loop_index": 0,
        "cat": item_value,
    }

    Draft202012Validator.check_schema(schema)
    assert Draft202012Validator(schema).is_valid(context_value)


def test_ref_sibling_constraints_remain_conjunctive() -> None:
    """A sibling keyword may tighten, but never replace, its referenced target."""
    from wf_core.analysis.context_scopes import context_schema_for_node

    workflow = _workflow(
        start="names",
        nodes=[
            _foreach("names", over="state.names", alias="name"),
            _node("body"),
        ],
        edges=[
            {"from": "names", "outcome": "loop", "to": "body"},
            {"from": "body", "outcome": "ok", "to": "names"},
            {"from": "names", "outcome": "done", "to": END},
        ],
        state_schema={
            "type": "object",
            "properties": {
                "names": {
                    "type": "array",
                    "items": {
                        "$ref": "#/$defs/ShortName",
                        "maxLength": 10,
                    },
                },
            },
            "$defs": {"ShortName": {"type": "string", "maxLength": 5}},
        },
    )
    schema = context_schema_for_node(workflow, "body")
    item = schema["properties"]["foreach"]["properties"]["names"]["properties"]["item"]
    validator = Draft202012Validator(item)

    assert validator.is_valid("12345")
    assert not validator.is_valid("123456")
