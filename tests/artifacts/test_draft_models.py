from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from wf_artifacts.drafts import (
    DraftChooseStep,
    DraftEndStep,
    DraftForeachStep,
    DraftInterruptStep,
    DraftMatchStep,
    DraftSubgraphStep,
    DraftUseStep,
    DraftWhenStep,
    WorkflowDraft,
)


def test_workflow_draft_uses_keyed_steps() -> None:
    draft = WorkflowDraft.model_validate(_keyed_echo_draft())

    assert isinstance(draft.steps["echo"], DraftUseStep)
    assert draft.steps["echo"].use == "demo.echo"


def test_workflow_draft_accepts_legacy_use_maps_but_dumps_canonical_bindings() -> None:
    draft = WorkflowDraft.model_validate(
        {
            **_keyed_echo_draft(),
            "steps": {
                "echo": {
                    "use": "demo.echo",
                    "in": {"input.text": "text"},
                    "with": {"limit": 3},
                    "out": {"echoed": "state.echoed"},
                }
            },
        }
    )

    dumped = draft.model_dump(mode="json")

    assert "in" not in dumped["steps"]["echo"]
    assert "with" not in dumped["steps"]["echo"]
    assert "out" not in dumped["steps"]["echo"]
    assert dumped["steps"]["echo"]["input"][0]["target"] == "limit"
    assert dumped["steps"]["echo"]["input"][1]["path"] == "input.text"
    assert dumped["steps"]["echo"]["output"][0]["target"] == "state.echoed"


def test_workflow_draft_accepts_legacy_interrupt_maps_but_dumps_canonical_bindings() -> (
    None
):
    draft = WorkflowDraft.model_validate(
        {
            **_keyed_echo_draft(),
            "start": "approval",
            "steps": {
                "approval": {
                    "interrupt": {
                        "kind": "approval",
                        "request": {"input.text": "message"},
                        "resume": {"approved": "state.approved"},
                    }
                },
            },
            "routes": {"approval": {"submitted": "__end__"}},
        }
    )

    dumped = draft.model_dump(mode="json")

    assert (
        dumped["steps"]["approval"]["interrupt"]["request"][0]["path"] == "input.text"
    )
    assert dumped["steps"]["approval"]["interrupt"]["request"][0]["target"] == "message"
    assert dumped["steps"]["approval"]["interrupt"]["resume"][0]["source"] == "approved"
    assert (
        dumped["steps"]["approval"]["interrupt"]["resume"][0]["target"]
        == "state.approved"
    )


def test_workflow_draft_preserves_typed_interrupt_contracts() -> None:
    request_schema = {
        "type": "object",
        "properties": {"issues": {"type": "array"}},
        "required": ["issues"],
    }
    resume_schema = {
        "type": "object",
        "properties": {"selected": {"type": "array"}},
        "required": ["selected"],
    }
    draft = WorkflowDraft.model_validate(
        {
            **_keyed_echo_draft(),
            "start": "review",
            "steps": {
                "review": {
                    "interrupt": {
                        "kind": "issue_review",
                        "request_schema": request_schema,
                        "resume_schema": resume_schema,
                        "outcomes": ["submitted", "cancelled"],
                    }
                }
            },
        }
    )

    step = draft.steps["review"]
    dumped = draft.model_dump(mode="json", by_alias=True)

    assert isinstance(step, DraftInterruptStep)
    assert step.interrupt.request_schema is not None
    assert step.interrupt.request_schema.type == "object"
    assert step.interrupt.request_schema.properties == {"issues": {"type": "array"}}
    assert step.interrupt.resume_schema is not None
    assert step.interrupt.resume_schema.required == ["selected"]
    assert dumped["steps"]["review"]["interrupt"]["request_schema"] == request_schema
    assert dumped["steps"]["review"]["interrupt"]["resume_schema"] == resume_schema


def test_workflow_draft_rejects_non_object_interrupt_contracts() -> None:
    with pytest.raises(ValidationError, match="interrupt schema must describe"):
        WorkflowDraft.model_validate(
            {
                **_keyed_echo_draft(),
                "start": "review",
                "steps": {
                    "review": {
                        "interrupt": {
                            "kind": "issue_review",
                            "request_schema": {"type": "array"},
                        }
                    }
                },
            }
        )


def test_workflow_draft_preserves_subgraph_workflow_boundaries() -> None:
    child_report = {
        "workflow": {"artifact_id": "child_report", "version": 2},
        "input_schema": {
            "type": "object",
            "properties": {"topic": {"type": "string"}},
        },
        "output_schema": {
            "type": "object",
            "properties": {"report": {"type": "string"}},
        },
        "input": [{"target": "topic", "path": "state.topic"}],
        "output": [{"source": "report", "target": "state.report"}],
        "outcomes": ["ok", "error"],
    }
    for step_id, subgraph in [
        (
            "child",
            {"workflow": {"name": "child"}, "outcomes": ["ok"]},
        ),
        ("child_report", child_report),
    ]:
        draft = WorkflowDraft.model_validate(
            {
                **_keyed_echo_draft(),
                "start": step_id,
                "steps": {step_id: {"subgraph": subgraph}},
            }
        )

        step = draft.steps[step_id]
        dumped = draft.model_dump(mode="json", by_alias=True)

        assert isinstance(step, DraftSubgraphStep)
        dumped_subgraph = dumped["steps"][step_id]["subgraph"]
        assert dumped_subgraph["workflow"] == subgraph["workflow"]
        assert dumped_subgraph["outcomes"] == subgraph["outcomes"]
        if step_id == "child_report":
            assert dumped_subgraph["input_schema"]["type"] == "object"
            assert dumped_subgraph["input_schema"]["properties"] == {
                "topic": {"type": "string"}
            }
            assert dumped_subgraph["output_schema"]["type"] == "object"
            assert dumped_subgraph["output_schema"]["properties"] == {
                "report": {"type": "string"}
            }
            assert dumped_subgraph["input"] == child_report["input"]
            assert dumped_subgraph["output"] == child_report["output"]


def test_draft_step_requires_exactly_one_kind_key() -> None:
    draft = _keyed_echo_draft()
    steps = draft["steps"]
    assert isinstance(steps, dict)
    echo = steps["echo"]
    assert isinstance(echo, dict)
    echo["join"] = {}

    with pytest.raises(ValidationError) as exc_info:
        WorkflowDraft.model_validate(draft)

    assert "steps.echo" in str(exc_info.value)


def test_workflow_draft_accepts_when_step() -> None:
    draft = WorkflowDraft.model_validate(
        {
            **_keyed_echo_draft(),
            "start": "decide",
            "steps": {
                **_keyed_echo_draft()["steps"],
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
            },
        }
    )

    assert isinstance(draft.steps["decide"], DraftWhenStep)


def test_workflow_draft_accepts_explicit_end_step() -> None:
    draft = WorkflowDraft.model_validate(
        {
            **_keyed_echo_draft(),
            "outcomes": ["ok", "error"],
            "steps": {
                **_keyed_echo_draft()["steps"],
                "end_error": {"end": {"outcome": "error"}},
            },
            "routes": {"echo": {"error": "end_error"}},
        }
    )

    terminal = draft.steps["end_error"]

    assert isinstance(terminal, DraftEndStep)
    assert terminal.end.outcome == "error"


def test_workflow_draft_accepts_choose_step() -> None:
    draft = WorkflowDraft.model_validate(
        {
            **_keyed_echo_draft(),
            "start": "choose_next",
            "steps": {
                **_keyed_echo_draft()["steps"],
                "choose_next": {
                    "choose": {
                        "clauses": [
                            {
                                "if": {
                                    "op": "exists",
                                    "path": "state.text",
                                },
                                "then": "echo",
                            }
                        ],
                        "default": "__end__",
                    }
                },
            },
        }
    )

    assert isinstance(draft.steps["choose_next"], DraftChooseStep)


def test_workflow_draft_foreach_over_dumps_structural_path() -> None:
    draft = WorkflowDraft.model_validate(
        {
            **_keyed_echo_draft(),
            "start": "each_item",
            "steps": {
                **_keyed_echo_draft()["steps"],
                "each_item": {
                    "foreach": {
                        "over": "state.items",
                        "as": "item",
                    }
                },
            },
            "routes": {
                "each_item": {"loop": "echo", "done": "__end__"},
                "echo": {"ok": "__end__"},
            },
        }
    )

    dumped = draft.model_dump(mode="json")

    assert dumped["steps"]["each_item"]["foreach"]["over"] == "state.items"


def test_workflow_draft_foreach_accepts_canonical_item_error_policy() -> None:
    draft = WorkflowDraft.model_validate(
        {
            **_keyed_echo_draft(),
            "start": "each_item",
            "steps": {
                "each_item": {
                    "foreach": {
                        "over": "state.items",
                        "as": "item",
                        "mode": "concurrent",
                        "concurrent": {"max_active": 2, "max_outstanding": 3},
                        "item_error": {
                            "action": "collect",
                            "collect_to": "state.item_errors",
                        },
                    }
                }
            },
            "routes": {"each_item": {"loop": "__end__", "done": "__end__"}},
        }
    )

    step = draft.steps["each_item"]
    dumped = draft.model_dump(mode="json")

    assert isinstance(step, DraftForeachStep)
    assert dumped["steps"]["each_item"]["foreach"]["item_error"] == {
        "action": "collect",
        "collect_to": "state.item_errors",
    }
    assert "on_item_error" not in dumped["steps"]["each_item"]["foreach"]


def test_workflow_draft_foreach_accepts_item_error_action_string() -> None:
    draft = WorkflowDraft.model_validate(
        {
            **_keyed_echo_draft(),
            "start": "each_item",
            "steps": {
                "each_item": {
                    "foreach": {
                        "over": "state.items",
                        "as": "item",
                        "item_error": "skip",
                    }
                }
            },
            "routes": {"each_item": {"loop": "__end__", "done": "__end__"}},
        }
    )

    dumped = draft.model_dump(mode="json")

    assert dumped["steps"]["each_item"]["foreach"]["item_error"]["action"] == "skip"


def test_workflow_draft_foreach_collect_string_requires_destination() -> None:
    with pytest.raises(ValidationError, match="collect_to"):
        WorkflowDraft.model_validate(
            {
                **_keyed_echo_draft(),
                "start": "each_item",
                "steps": {
                    "each_item": {
                        "foreach": {
                            "over": "state.items",
                            "as": "item",
                            "item_error": "collect",
                        }
                    }
                },
            }
        )


def test_workflow_draft_accepts_match_step() -> None:
    draft = WorkflowDraft.model_validate(
        {
            **_keyed_echo_draft(),
            "start": "match_status",
            "steps": {
                **_keyed_echo_draft()["steps"],
                "match_status": {
                    "match": {
                        "value": "state.status",
                        "cases": [
                            {"equals": "ready", "then": "echo"},
                            {"equals": "done", "then": "__end__"},
                        ],
                        "default": "__end__",
                    }
                },
            },
        }
    )

    assert isinstance(draft.steps["match_status"], DraftMatchStep)


def _keyed_echo_draft() -> dict[str, Any]:
    return {
        "name": "echo",
        "input_schema": {},
        "state_schema": {"fields": {}},
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
