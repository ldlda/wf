from __future__ import annotations

import warnings

from wf_core import RunStatus

from examples.wrapper_status_route import build_wrapper
from examples.wrapper_normalization import build_normalized_wrapper


def test_status_wrapper_uses_match_without_deprecation_warning() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        workflow = build_wrapper()

    run = workflow.execute({"text": "hello"})

    assert run.status == RunStatus.COMPLETED
    assert run.output["message"] == "HELLO"


def test_normalized_wrapper_maps_raw_status_to_workflow_outcome() -> None:
    workflow = build_normalized_wrapper()

    success = workflow.execute({"text": "hello"})
    needs_input = workflow.execute({"text": "clarify?"})
    failed = workflow.execute({"text": ""})

    assert success.status == RunStatus.COMPLETED
    assert success.trace[-1].outcome == "done"
    assert success.output["message"] == "HELLO"
    assert needs_input.status == RunStatus.COMPLETED
    assert needs_input.trace[-1].outcome == "needs_input"
    assert needs_input.output["message"] == "Need clarification"
    assert failed.status == RunStatus.COMPLETED
    assert failed.trace[-1].outcome == "failed"
    assert failed.output["message"] == "No text supplied"
