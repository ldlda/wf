from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from wf_artifacts.drafts import (
    DraftChooseStep,
    DraftUseStep,
    DraftWhenStep,
    WorkflowDraft,
)


def test_workflow_draft_uses_keyed_steps() -> None:
    draft = WorkflowDraft.model_validate(_keyed_echo_draft())

    assert isinstance(draft.steps["echo"], DraftUseStep)
    assert draft.steps["echo"].use == "demo.echo"


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
                "in": {"input.text": "text"},
                "out": {"echoed": "state.echoed"},
            }
        },
        "routes": {"echo": {"ok": "__end__"}},
    }
