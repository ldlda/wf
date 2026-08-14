from __future__ import annotations

from wf_api.authoring_contracts import (
    project_authoring_contract_inventory,
    schema_path_options,
)


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


def test_project_authoring_contract_inventory_composes_pure_inputs() -> None:
    context_entry = {
        "path": "context.loop_item",
        "label": "Loop Item",
        "origin": "runtime_context",
        "schema": {"type": "string"},
        "required": False,
        "availability": "conditional",
        "uses": ["step_input"],
        "reason": "Only available inside the foreach body.",
    }
    step_input_target = {
        "path": "step.input.query",
        "label": "Query",
        "origin": "step_input",
        "schema": {"type": "string"},
        "required": True,
        "availability": "available",
        "uses": ["step_input"],
    }
    step_output_source = {
        "path": "step.output.answer",
        "label": "Answer",
        "origin": "step_output",
        "schema": {"type": "string"},
        "required": False,
        "availability": "available",
        "uses": ["step_output_source", "workflow_output"],
    }
    entry_step = {
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
            "uses": ["step_input", "step_output_source", "workflow_output"],
        },
    ]
    assert inventory["step_input_targets"] == [step_input_target]
    assert inventory["step_output_sources"] == [step_output_source]
    assert inventory["state_targets"][0]["path"] == "state.answer"
    assert inventory["workflow_output_targets"][0]["path"] == "output.result"
    assert inventory["entry_steps"] == [entry_step]
    assert inventory["workflow_outcomes"] == ["ok", "error"]
    assert inventory["warnings"] == ["selected step has conditional context"]
