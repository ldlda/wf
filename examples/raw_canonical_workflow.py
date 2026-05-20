from __future__ import annotations

from wf_core import END, RuntimeContext, Workflow, execute_workflow
from wf_core.run_state import RunState


def build_raw_canonical_workflow() -> Workflow:
    """Build a raw core workflow using the canonical post-migration shape."""
    return Workflow.model_validate(
        {
            "name": "raw_canonical_echo",
            "input_schema": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
            "state_schema": {
                "fields": [
                    {
                        "path": "state.message",
                        "schema": {"type": "string"},
                        "reducer": {"name": "wf.std.replace"},
                    }
                ]
            },
            "output_schema": {
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
            },
            "node_defs": [
                {
                    "name": "format_text",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "prefix": {"type": "string"},
                        },
                        "required": ["text", "prefix"],
                    },
                    "output_schema": {
                        "type": "object",
                        "properties": {"message": {"type": "string"}},
                        "required": ["message"],
                    },
                    "outcomes": ["ok"],
                }
            ],
            "start": "format",
            "nodes": [
                {
                    "id": "format",
                    "type": "node",
                    "node": "format_text",
                    "input": [
                        {"target": "text", "path": "input.text"},
                        {"target": "prefix", "value": "raw:"},
                    ],
                    "output": [{"source": "message", "target": "state.message"}],
                }
            ],
            "edges": [{"from": "format", "outcome": "ok", "to": END}],
        }
    )


def build_raw_canonical_registry():
    """Return handlers for the raw canonical workflow example."""

    def format_text(payload: dict[str, object], _context: RuntimeContext):
        text = str(payload["text"]).upper()
        prefix = str(payload["prefix"])
        return {"message": f"{prefix}{text}"}

    return {"format_text": format_text}


def run_raw_canonical_example(text: str = "hello") -> RunState:
    workflow = build_raw_canonical_workflow()
    workflow.validate_structure().raise_for_errors()
    return execute_workflow(workflow, {"text": text}, build_raw_canonical_registry())
