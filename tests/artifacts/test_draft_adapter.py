from __future__ import annotations

from pydantic import ValidationError

from wf_artifacts.drafts import WorkflowDraft
from wf_artifacts.drafts.api import compile_workflow_draft, validate_workflow_draft
from wf_artifacts.drafts.adapter import build_workflow_from_draft
from wf_core import ConditionNode, ForeachNode, NodeUse
from wf_core.models.steps import InputValueBinding


def test_adapter_lowers_keyed_use_steps_and_routes_through_builder() -> None:
    draft = WorkflowDraft.model_validate(
        {
            "name": "echo",
            "input_schema": {},
            "state_schema": {"fields": {}},
            "output_schema": {},
            "start": "echo",
            "steps": {"echo": {"use": "demo.echo"}},
            "routes": {"echo": {"ok": "__end__"}},
        }
    )

    workflow = build_workflow_from_draft(draft)

    node = workflow.nodes[0]
    assert isinstance(node, NodeUse)
    assert node.id == "echo"
    assert node.node == "demo.echo"
    assert workflow.edges[0].from_ == "echo"
    assert workflow.edges[0].outcome == "ok"
    assert workflow.edges[0].to == "__end__"


def test_adapter_lowers_use_steps_to_canonical_bindings() -> None:
    draft = WorkflowDraft.model_validate(
        {
            "name": "echo",
            "input_schema": {},
            "state_schema": {"fields": {"echoed": {"type": "string"}}},
            "output_schema": {},
            "start": "echo",
            "steps": {
                "echo": {
                    "use": "demo.echo",
                    "input": [
                        {
                            "target": {"root": "local", "parts": ["text"]},
                            "path": {"root": "input", "parts": ["text"]},
                        }
                    ],
                    "output": [
                        {
                            "source": {"root": "local", "parts": ["echoed"]},
                            "target": {"root": "state", "parts": ["echoed"]},
                        }
                    ],
                }
            },
            "routes": {"echo": {"ok": "__end__"}},
        }
    )

    workflow = build_workflow_from_draft(draft)
    node = workflow.nodes[0]

    assert isinstance(node, NodeUse)
    dumped = node.model_dump(mode="json")
    assert "in_map" not in dumped
    assert "out_map" not in dumped
    assert dumped["input"][0]["target"] == {"root": "local", "parts": ["text"]}
    assert dumped["input"][0]["path"] == {"root": "input", "parts": ["text"]}
    assert dumped["output"][0]["source"] == {"root": "local", "parts": ["echoed"]}
    assert dumped["output"][0]["target"] == {"root": "state", "parts": ["echoed"]}


def test_adapter_lowers_static_inputs_for_constant_like_steps() -> None:
    draft = WorkflowDraft.model_validate(
        {
            "name": "constant",
            "input_schema": {},
            "state_schema": {"fields": {"message": {"type": "string"}}},
            "output_schema": {},
            "start": "constant",
            "steps": {
                "constant": {
                    "use": "wf.std.constant",
                    "input": [
                        {
                            "target": {"root": "local", "parts": ["value"]},
                            "value": "CLICKED",
                        }
                    ],
                    "output": [
                        {
                            "source": {"root": "local", "parts": ["value"]},
                            "target": {"root": "state", "parts": ["message"]},
                        }
                    ],
                }
            },
            "routes": {"constant": {"ok": "__end__"}},
        }
    )

    workflow = build_workflow_from_draft(draft)
    node = workflow.nodes[0]

    assert isinstance(node, NodeUse)
    assert node.node == "wf.std.constant"
    assert len(node.input) == 1
    assert isinstance(node.input[0], InputValueBinding)
    assert str(node.input[0].target) == "value"
    assert node.input[0].value == "CLICKED"


def test_invalid_literal_input_map_does_not_fall_through_to_join() -> None:
    draft = {
        "name": "bad_constant",
        "input_schema": {},
        "state_schema": {"fields": {}},
        "output_schema": {},
        "start": "constant",
        "steps": {
            "constant": {
                "use": "wf.std.constant",
                "in": {"value": {"value": "CLICKED"}},
            }
        },
        "routes": {"constant": {"ok": "__end__"}},
    }

    result = validate_workflow_draft(draft)

    assert result["status"] == "invalid"
    assert "steps.constant" in result["diagnostics"][0]["path"]
    try:
        compile_workflow_draft(draft)
    except ValidationError:
        pass
    else:  # pragma: no cover - kept explicit because silent join fallback was the bug.
        raise AssertionError("invalid use step compiled instead of failing")


def test_adapter_lowers_when_step_through_builder() -> None:
    draft = WorkflowDraft.model_validate(
        {
            "name": "when_example",
            "input_schema": {},
            "state_schema": {"fields": {}},
            "output_schema": {},
            "start": "decide",
            "steps": {
                "decide": {
                    "when": {
                        "if": {
                            "op": "ge",
                            "left": {"path": "state.count"},
                            "right": {"value": 1},
                        },
                        "then": "echo",
                        "otherwise": "__end__",
                    }
                },
                "echo": {"use": "demo.echo"},
            },
            "routes": {"echo": {"ok": "__end__"}},
        }
    )

    workflow = build_workflow_from_draft(draft)
    condition = workflow.nodes[0]

    assert isinstance(condition, ConditionNode)
    assert condition.id == "decide"
    assert workflow.start == "decide"
    assert [(edge.from_, edge.outcome, edge.to) for edge in workflow.edges[:2]] == [
        ("decide", "true", "echo"),
        ("decide", "false", "__end__"),
    ]


def test_adapter_lowers_choose_step_through_builder() -> None:
    draft = WorkflowDraft.model_validate(
        {
            "name": "choose_example",
            "input_schema": {},
            "state_schema": {"fields": {}},
            "output_schema": {},
            "start": "pick",
            "steps": {
                "pick": {
                    "choose": {
                        "clauses": [
                            {
                                "if": {
                                    "op": "gt",
                                    "left": {"path": "state.score"},
                                    "right": {"value": 80},
                                },
                                "then": "high",
                            },
                            {
                                "if": {
                                    "op": "exists",
                                    "path": "state.fallback",
                                },
                                "then": "fallback",
                            },
                        ],
                        "default": "__end__",
                    }
                },
                "high": {"use": "demo.high"},
                "fallback": {"use": "demo.fallback"},
            },
            "routes": {
                "high": {"ok": "__end__"},
                "fallback": {"ok": "__end__"},
            },
        }
    )

    workflow = build_workflow_from_draft(draft)
    condition_ids = [
        node.id for node in workflow.nodes if isinstance(node, ConditionNode)
    ]

    assert condition_ids == ["pick", "pick_2"]
    assert workflow.start == "pick"
    assert [(edge.from_, edge.outcome, edge.to) for edge in workflow.edges[:4]] == [
        ("pick", "true", "high"),
        ("pick", "false", "pick_2"),
        ("pick_2", "true", "fallback"),
        ("pick_2", "false", "__end__"),
    ]


def test_adapter_lowers_match_step_through_builder() -> None:
    draft = WorkflowDraft.model_validate(
        {
            "name": "match_example",
            "input_schema": {},
            "state_schema": {"fields": {}},
            "output_schema": {},
            "start": "match_status",
            "steps": {
                "match_status": {
                    "match": {
                        "value": "state.status",
                        "cases": [
                            {"equals": "ready", "then": "ready"},
                            {"equals": "waiting", "then": "waiting"},
                        ],
                        "default": "__end__",
                    }
                },
                "ready": {"use": "demo.ready"},
                "waiting": {"use": "demo.waiting"},
            },
            "routes": {
                "ready": {"ok": "__end__"},
                "waiting": {"ok": "__end__"},
            },
        }
    )

    workflow = build_workflow_from_draft(draft)
    condition_ids = [
        node.id for node in workflow.nodes if isinstance(node, ConditionNode)
    ]

    assert condition_ids == ["match_status", "match_status_2"]
    assert workflow.start == "match_status"
    assert [(edge.from_, edge.outcome, edge.to) for edge in workflow.edges[:4]] == [
        ("match_status", "true", "ready"),
        ("match_status", "false", "match_status_2"),
        ("match_status_2", "true", "waiting"),
        ("match_status_2", "false", "__end__"),
    ]


def test_adapter_lowers_foreach_policy_through_builder() -> None:
    draft = WorkflowDraft.model_validate(
        {
            "name": "foreach_policy",
            "input_schema": {},
            "state_schema": {
                "type": "object",
                "properties": {
                    "items": {"type": "array"},
                    "item_errors": {"type": "array"},
                },
            },
            "output_schema": {},
            "start": "each_item",
            "steps": {
                "each_item": {
                    "foreach": {
                        "over": "state.items",
                        "as": "item",
                        "mode": "concurrent",
                        "concurrent": {"max_active": 2, "max_outstanding": 4},
                        "item_error": {
                            "action": "collect",
                            "collect_to": "state.item_errors",
                        },
                    }
                }
            },
            "routes": {
                "each_item": {
                    "loop": "__end__",
                    "done": "__end__",
                    "completed_with_errors": "__end__",
                }
            },
        }
    )

    workflow = build_workflow_from_draft(draft)
    foreach = workflow.nodes[0]

    assert isinstance(foreach, ForeachNode)
    assert foreach.mode == "concurrent"
    assert foreach.concurrent is not None
    assert foreach.concurrent.max_active == 2
    assert foreach.concurrent.max_outstanding == 4
    assert foreach.item_error.action == "collect"
    assert str(foreach.item_error.collect_to) == "state.item_errors"
