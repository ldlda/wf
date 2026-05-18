from __future__ import annotations

import pytest
from pydantic import ValidationError

from wf_artifacts.drafts import DraftUseStep, WorkflowDraft


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


def _keyed_echo_draft() -> dict[str, object]:
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
