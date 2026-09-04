from __future__ import annotations

from wf_api.authoring_contracts import (
    context_path_options,
    project_authoring_contract_inventory,
    project_authoring_step_contract,
    schema_path_options,
)
from wf_api.models import AuthoringPathOptionPayload, AuthoringStepContractPayload


def test_schema_path_options_is_parent_first_and_schema_derived() -> None:
    schema = {
        "type": "object",
        "properties": {
            "request": {
                "title": "Request",
                "description": "The incoming request.",
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "metadata": {
                        "type": "object",
                        "additionalProperties": True,
                    },
                },
                "required": ["id"],
            },
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                },
            },
            "headers": {
                "type": "object",
                "additionalProperties": {"type": "string"},
            },
        },
        "required": ["request", "items"],
    }

    options = schema_path_options(
        schema,
        root="input",
        uses=["step_input", "workflow_output"],
    )

    assert options == [
        {
            "path": "input.request",
            "label": "Request",
            "origin": "workflow_input",
            "schema": {
                "title": "Request",
                "description": "The incoming request.",
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "metadata": {"type": "object", "additionalProperties": True},
                },
                "required": ["id"],
            },
            "required": True,
            "availability": "available",
            "uses": ["step_input", "workflow_output"],
            "description": "The incoming request.",
        },
        {
            "path": "input.request.id",
            "label": "Id",
            "origin": "workflow_input",
            "schema": {"type": "string"},
            "required": True,
            "availability": "available",
            "uses": ["step_input", "workflow_output"],
        },
        {
            "path": "input.request.metadata",
            "label": "Metadata",
            "origin": "workflow_input",
            "schema": {"type": "object", "additionalProperties": True},
            "required": False,
            "availability": "available",
            "uses": ["step_input", "workflow_output"],
        },
        {
            "path": "input.items",
            "label": "Items",
            "origin": "workflow_input",
            "schema": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                },
            },
            "required": True,
            "availability": "available",
            "uses": ["step_input", "workflow_output"],
        },
        {
            "path": "input.headers",
            "label": "Headers",
            "origin": "workflow_input",
            "schema": {
                "type": "object",
                "additionalProperties": {"type": "string"},
            },
            "required": False,
            "availability": "available",
            "uses": ["step_input", "workflow_output"],
        },
    ]
    assert not any("*" in option["path"] for option in options)
    assert not any(option["path"].startswith("input.metadata.") for option in options)
    assert options[0] == {
        "path": "input.request",
        "label": "Request",
        "origin": "workflow_input",
        "schema": {
            "title": "Request",
            "description": "The incoming request.",
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "metadata": {"type": "object", "additionalProperties": True},
            },
            "required": ["id"],
        },
        "required": True,
        "availability": "available",
        "uses": ["step_input", "workflow_output"],
        "description": "The incoming request.",
    }


def test_schema_path_options_resolves_local_definition_metadata() -> None:
    options = schema_path_options(
        {
            "type": "object",
            "properties": {"snapshot": {"$ref": "#/$defs/Snapshot"}},
            "required": ["snapshot"],
            "$defs": {
                "Snapshot": {
                    "title": "Saved Snapshot",
                    "type": "object",
                    "properties": {"version": {"type": "integer"}},
                    "required": ["version"],
                }
            },
        },
        root="input",
        uses=["step_input"],
    )

    assert options == [
        {
            "path": "input.snapshot",
            "label": "Saved Snapshot",
            "origin": "workflow_input",
            "schema": {
                "$ref": "#/$defs/Snapshot",
                "$defs": {
                    "Snapshot": {
                        "title": "Saved Snapshot",
                        "type": "object",
                        "properties": {"version": {"type": "integer"}},
                        "required": ["version"],
                    }
                },
            },
            "required": True,
            "availability": "available",
            "uses": ["step_input"],
        },
        {
            "path": "input.snapshot.version",
            "label": "Version",
            "origin": "workflow_input",
            "schema": {
                "type": "integer",
                "$defs": {
                    "Snapshot": {
                        "title": "Saved Snapshot",
                        "type": "object",
                        "properties": {"version": {"type": "integer"}},
                        "required": ["version"],
                    }
                },
            },
            "required": True,
            "availability": "available",
            "uses": ["step_input"],
        },
    ]


def test_schema_path_options_stops_expanding_recursive_local_definition() -> None:
    options = schema_path_options(
        {
            "type": "object",
            "properties": {"node": {"$ref": "#/$defs/Node"}},
            "$defs": {
                "Node": {
                    "type": "object",
                    "properties": {"child": {"$ref": "#/$defs/Node"}},
                }
            },
        },
        root="input",
        uses=["step_input"],
    )

    assert [option["path"] for option in options] == [
        "input.node",
        "input.node.child",
    ]


def test_schema_path_options_bounds_deep_inline_objects() -> None:
    schema: dict[str, object] = {"type": "object", "properties": {}}
    current = schema
    for index in range(60):
        child: dict[str, object] = {"type": "object", "properties": {}}
        current["properties"] = {f"level_{index}": child}
        current = child

    options = schema_path_options(schema, root="input", uses=["step_input"])

    assert len(options) == 32


def test_schema_path_options_returns_empty_schema_for_unconstrained_property() -> None:
    options = schema_path_options(
        {
            "type": "object",
            "properties": {"value": {}},
        },
        root="state",
        uses=["state_target"],
    )

    assert options == [
        {
            "path": "state.value",
            "label": "Value",
            "origin": "workflow_state",
            "schema": {},
            "required": False,
            "availability": "available",
            "uses": ["state_target"],
        }
    ]


def test_schema_path_options_copies_schema_fragments() -> None:
    schema = {
        "type": "object",
        "properties": {
            "request": {
                "type": "object",
                "properties": {"id": {"type": "string"}},
            }
        },
    }

    options = schema_path_options(schema, root="input", uses=["step_input"])
    # Options are safe for UI consumers to annotate without mutating the source schema.
    options[0]["schema"]["title"] = "Edited through option"

    assert schema["properties"]["request"].get("title") is None


def test_project_authoring_contract_inventory_composes_pure_inputs() -> None:
    context_entry: AuthoringPathOptionPayload = {
        "path": "context.loop_item",
        "label": "Loop Item",
        "origin": "runtime_context",
        "schema": {"type": "string"},
        "required": False,
        "availability": "conditional",
        "uses": ["step_input"],
        "reason": "Only available inside the foreach body.",
    }
    step_input_target: AuthoringPathOptionPayload = {
        "path": "step.input.query",
        "label": "Query",
        "origin": "step_input",
        "schema": {"type": "string"},
        "required": True,
        "availability": "available",
        "uses": ["step_input"],
    }
    step_output_source: AuthoringPathOptionPayload = {
        "path": "step.output.answer",
        "label": "Answer",
        "origin": "step_output",
        "schema": {"type": "string"},
        "required": False,
        "availability": "available",
        "uses": ["step_output_source", "workflow_output"],
    }
    entry_step: AuthoringStepContractPayload = {
        "step_id": "fetch",
        "label": "Fetch",
    }

    inventory = project_authoring_contract_inventory(
        workspace_id="workspace-1",
        revision=4,
        selected_step_id="fetch",
        input_schema={
            "type": "object",
            "properties": {"request": {"type": "string"}},
        },
        state_schema={
            "type": "object",
            "properties": {"answer": {"type": "string"}},
        },
        output_schema={
            "type": "object",
            "properties": {"result": {"type": "string"}},
        },
        context_entries=[context_entry],
        step_input_targets=[step_input_target],
        step_output_sources=[step_output_source],
        entry_steps=[entry_step],
        workflow_outcomes=["ok", "error"],
        warnings=["selected step has conditional context"],
    )

    assert inventory["workspace_id"] == "workspace-1"
    assert inventory["revision"] == 4
    assert inventory["selected_step_id"] == "fetch"
    assert inventory["readable_sources"] == [
        {
            "path": "input.request",
            "label": "Request",
            "origin": "workflow_input",
            "schema": {"type": "string"},
            "required": False,
            "availability": "available",
            "uses": ["step_input", "workflow_output"],
        },
        context_entry,
        {
            "path": "state.answer",
            "label": "Answer",
            "origin": "workflow_state",
            "schema": {"type": "string"},
            "required": False,
            "availability": "available",
            "uses": ["step_input", "workflow_output"],
        },
    ]
    assert inventory["step_input_targets"] == [step_input_target]
    assert inventory["step_output_sources"] == [step_output_source]
    assert inventory["state_targets"][0]["path"] == "state.answer"
    assert inventory["workflow_output_targets"][0]["path"] == "output.result"
    assert inventory["entry_steps"] == [entry_step]
    assert inventory["workflow_outcomes"] == ["ok", "error"]
    assert inventory["warnings"] == ["selected step has conditional context"]


def test_authoring_paths_exclude_incompatible_binding_roles() -> None:
    inventory = project_authoring_contract_inventory(
        workspace_id="workspace-1",
        revision=1,
        selected_step_id=None,
        input_schema={"type": "object"},
        state_schema={
            "type": "object",
            "properties": {"answer": {"type": "string"}},
        },
        output_schema={"type": "object"},
    )
    step_contract = project_authoring_step_contract(
        step_id="fetch",
        label="Fetch",
        description=None,
        input_schema={"type": "object"},
        output_schema={
            "type": "object",
            "properties": {"answer": {"type": "string"}},
        },
        outcomes=["ok"],
    )

    state_source = inventory["readable_sources"][0]
    assert state_source["path"] == "state.answer"
    assert "step_output_source" not in state_source["uses"]
    output_sources = step_contract.get("output_sources")
    assert output_sources is not None
    assert output_sources[0]["path"] == "step_output.answer"
    assert "workflow_output" not in output_sources[0]["uses"]


def test_context_path_options_are_step_input_only() -> None:
    options = context_path_options(
        [
            {
                "name": "loop_item",
                "schema": {"type": "string"},
                "description": "Current foreach item",
                "availability": "conditional",
                "reason": "Only available inside the foreach body.",
            }
        ]
    )

    assert options[0]["path"] == "context.loop_item"
    assert options[0]["origin"] == "runtime_context"
    assert options[0]["uses"] == ["step_input"]
    assert options[0]["availability"] == "conditional"
    reason = options[0].get("reason")
    assert reason == "Only available inside the foreach body."


def test_project_inventory_does_not_offer_context_for_workflow_output() -> None:
    context_entry: AuthoringPathOptionPayload = {
        "path": "context.item",
        "label": "Item",
        "origin": "runtime_context",
        "schema": {},
        "required": False,
        "availability": "available",
        "uses": ["step_input", "workflow_output"],
    }

    inventory = project_authoring_contract_inventory(
        workspace_id="workspace-1",
        revision=1,
        selected_step_id=None,
        input_schema={"type": "object"},
        state_schema={"type": "object"},
        output_schema={"type": "object"},
        context_entries=[context_entry],
    )

    assert inventory["readable_sources"][0]["path"] == "context.item"
    assert inventory["readable_sources"][0]["uses"] == ["step_input"]


def test_structured_foreach_paths_appear_in_authoring_inventory() -> None:
    from wf_api.authoring_contracts import context_path_options_for_node
    from wf_core import END, Edge, ForeachNode, NodeUse, SchemaRef, Workflow
    from wf_core.models.schemas import StateSchema

    def _foreach(node_id: str, *, over: str, alias: str) -> ForeachNode:
        return ForeachNode.model_validate(
            {"id": node_id, "type": "foreach", "over": over, "as": alias}
        )

    workflow = Workflow(
        name="inventory_structured",
        input_schema=SchemaRef(type="object"),
        state_schema=StateSchema.model_validate(
            {
                "type": "object",
                "properties": {
                    "customers": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"name": {"type": "string"}},
                        },
                    },
                    "orders": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"sku": {"type": "string"}},
                        },
                    },
                },
            }
        ),
        output_schema=SchemaRef(type="object"),
        start="customers",
        nodes=[
            _foreach("customers", over="state.customers", alias="customer"),
            _foreach("orders", over="state.orders", alias="order"),
            NodeUse(id="inner_body", type="node", node="noop"),
        ],
        edges=[
            Edge.model_validate(
                {"from": "customers", "outcome": "loop", "to": "orders"}
            ),
            Edge.model_validate(
                {"from": "orders", "outcome": "loop", "to": "inner_body"}
            ),
            Edge.model_validate({"from": "inner_body", "outcome": "ok", "to": "orders"}),
            Edge.model_validate({"from": "orders", "outcome": "done", "to": "customers"}),
            Edge.model_validate({"from": "customers", "outcome": "done", "to": END}),
        ],
    )
    options = context_path_options_for_node(workflow, "inner_body")
    paths = {option["path"] for option in options}
    assert "context.foreach.customers.item" in paths
    assert "context.foreach.customers.index" in paths
    assert "context.foreach.orders.item" in paths
    assert "context.foreach.orders.index" in paths
    for option in options:
        if option["path"].startswith("context.foreach."):
            assert option["origin"] == "runtime_context"
            assert option["uses"] == ["step_input"]
