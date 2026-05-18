from __future__ import annotations

from wf_artifacts.drafts import WorkflowDraft
from wf_artifacts.drafts.adapter import build_workflow_from_draft
from wf_core import ConditionNode, NodeUse


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
