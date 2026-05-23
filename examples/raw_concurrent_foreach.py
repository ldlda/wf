from __future__ import annotations

from wf_core import END, RuntimeContext, Workflow, execute_workflow
from wf_core.run_state import RunState


def build_raw_concurrent_foreach_workflow() -> Workflow:
    """Build the canonical JSON/Pydantic shape for concurrent foreach.

    This example is intentionally raw `wf_core`: it is useful for MCP/LLM-facing
    authoring surfaces that need to emit workflow JSON without Python builder
    helpers.
    """
    return Workflow.model_validate(
        {
            "name": "raw_concurrent_foreach",
            "input_schema": {
                "type": "object",
                "properties": {"items": {"type": "array"}},
                "required": ["items"],
            },
            "state_schema": {
                "type": "object",
                "properties": {
                    "items": {"type": "array"},
                    "seen": {
                        "type": "array",
                        "reducer": "wf.std.append",
                    },
                    "errors": {"type": "array"},
                },
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "seen": {"type": "array"},
                    "errors": {"type": "array"},
                },
            },
            "node_defs": [
                {
                    "name": "record_item",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "value": {},
                            "seen": {},
                        },
                        "required": ["value", "seen"],
                    },
                    "output_schema": {
                        "type": "object",
                        "properties": {"seen": {}},
                        "required": ["seen"],
                    },
                    "outcomes": ["ok"],
                }
            ],
            "start": "each",
            "nodes": [
                {
                    "id": "each",
                    "type": "foreach",
                    "over": {"root": "state", "parts": ["items"]},
                    "as": "item",
                    "mode": "concurrent",
                    "concurrent": {
                        "max_active": 2,
                        "max_outstanding": 2,
                    },
                    "item_error": {
                        "action": "collect",
                        "collect_to": {"root": "state", "parts": ["errors"]},
                    },
                },
                {
                    "id": "record",
                    "type": "node",
                    "node": "record_item",
                    "input": [
                        {
                            "target": {"root": "local", "parts": ["value"]},
                            "path": {"root": "context", "parts": ["item"]},
                        },
                        {
                            "target": {"root": "local", "parts": ["seen"]},
                            "path": {"root": "context", "parts": ["item"]},
                        },
                    ],
                    "output": [
                        {
                            "source": {"root": "local", "parts": ["seen"]},
                            "target": {"root": "state", "parts": ["seen"]},
                        }
                    ],
                },
            ],
            "edges": [
                {"from": "each", "outcome": "loop", "to": "record"},
                {"from": "record", "outcome": "ok", "to": END},
                {"from": "each", "outcome": "done", "to": END},
                {"from": "each", "outcome": "completed_with_errors", "to": END},
            ],
        }
    )


def build_raw_concurrent_foreach_registry():
    """Return handlers for the raw concurrent foreach example."""

    def record_item(
        payload: dict[str, object],
        _context: RuntimeContext,
    ) -> dict[str, object]:
        if payload["value"] == "bad":
            raise ValueError("bad item")
        return {"outcome": "ok", "output": {"seen": payload["seen"]}}

    return {"record_item": record_item}


def run_raw_concurrent_foreach_example() -> RunState:
    """Run raw concurrent foreach with collected item errors."""
    return execute_workflow(
        build_raw_concurrent_foreach_workflow(),
        {"items": ["a", "bad", "c"]},
        build_raw_concurrent_foreach_registry(),
    )


def main() -> None:
    """Run the example directly from the command line."""
    run = run_raw_concurrent_foreach_example()
    print(run.status.value, run.output)


if __name__ == "__main__":
    main()
