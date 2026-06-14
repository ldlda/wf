from __future__ import annotations

from pathlib import Path

import pytest

from examples.browser_click_workflow.ops import (
    CollectSnapshotsInput,
    OpenPageInput,
    WaitForClickInput,
    _active_session_count,
    _collect_snapshots,
    _open_click_page,
    _wait_for_click,
)
from wf_config import load_workflow_config
from wf_server.config import build_workflow_server_from_workflow_config


def test_browser_click_source_simulates_click_and_cleans_up() -> None:
    opened = _open_click_page(
        OpenPageInput(button_label="Launch Workflow", open_browser=False)
    )

    assert opened.before.clicked is False
    assert opened.before.button_text == "Launch Workflow"
    assert opened.before.status_text == "Waiting for click"

    clicked = _wait_for_click(
        WaitForClickInput(
            session_id=opened.session_id, simulate=True, timeout_seconds=2
        )
    )
    result = _collect_snapshots(
        CollectSnapshotsInput(
            session_id=opened.session_id,
            before=opened.before,
            after=clicked.after,
        )
    )

    assert result.before.clicked is False
    assert result.after.clicked is True
    assert result.after.status_text == "Button clicked"
    assert result.closed is True
    assert _active_session_count() == 0


def test_browser_click_source_human_timeout_cleans_up() -> None:
    opened = _open_click_page(OpenPageInput(open_browser=False))

    with pytest.raises(TimeoutError, match="timed out waiting for click"):
        _wait_for_click(
            WaitForClickInput(
                session_id=opened.session_id,
                simulate=False,
                timeout_seconds=0.01,
            )
        )

    _collect_snapshots(
        CollectSnapshotsInput(
            session_id=opened.session_id,
            before=opened.before,
            after=opened.before,
        )
    )
    assert _active_session_count() == 0


EXAMPLE_DIR = Path(__file__).resolve().parents[2] / "examples" / "browser_click_workflow"


@pytest.mark.asyncio
async def test_browser_click_workflow_artifact_deployment_run_path(tmp_path) -> None:
    config = load_workflow_config(EXAMPLE_DIR / "wf.config.json")
    config.server.store.root = tmp_path / "store"
    server = build_workflow_server_from_workflow_config(config)

    plan = {
        "name": "browser_click_case_study",
        "input_schema": {
            "type": "object",
            "properties": {
                "button_label": {"type": "string"},
                "open_browser": {"type": "boolean"},
                "simulate": {"type": "boolean"},
                "timeout_seconds": {"type": "number"},
            },
            "required": ["button_label", "open_browser", "simulate", "timeout_seconds"],
        },
        "state_schema": {
            "type": "object",
            "properties": {
                "opened": {"type": "object", "reducer": "wf.std.replace"},
                "clicked": {"type": "object", "reducer": "wf.std.replace"},
                "result": {"type": "object", "reducer": "wf.std.replace"},
            },
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "before": {"type": "object"},
                "after": {"type": "object"},
                "closed": {"type": "boolean"},
            },
            "required": ["before", "after", "closed"],
        },
        "outcomes": ["ok"],
        "start": "open",
        "nodes": [
            {
                "id": "open",
                "type": "node",
                "node": "local.browser_click.open_click_page",
                "input": [
                    {
                        "path": {"root": "input", "parts": ["button_label"]},
                        "target": {"root": "local", "parts": ["button_label"]},
                    },
                    {
                        "path": {"root": "input", "parts": ["open_browser"]},
                        "target": {"root": "local", "parts": ["open_browser"]},
                    },
                ],
                "output": [
                    {
                        "source": {"root": "local", "parts": []},
                        "target": {"root": "state", "parts": ["opened"]},
                    }
                ],
            },
            {
                "id": "wait",
                "type": "node",
                "node": "local.browser_click.wait_for_click",
                "input": [
                    {
                        "path": {"root": "state", "parts": ["opened", "session_id"]},
                        "target": {"root": "local", "parts": ["session_id"]},
                    },
                    {
                        "path": {"root": "input", "parts": ["simulate"]},
                        "target": {"root": "local", "parts": ["simulate"]},
                    },
                    {
                        "path": {"root": "input", "parts": ["timeout_seconds"]},
                        "target": {"root": "local", "parts": ["timeout_seconds"]},
                    },
                ],
                "output": [
                    {
                        "source": {"root": "local", "parts": []},
                        "target": {"root": "state", "parts": ["clicked"]},
                    }
                ],
            },
            {
                "id": "collect",
                "type": "node",
                "node": "local.browser_click.collect_snapshots",
                "input": [
                    {
                        "path": {"root": "state", "parts": ["opened", "session_id"]},
                        "target": {"root": "local", "parts": ["session_id"]},
                    },
                    {
                        "path": {"root": "state", "parts": ["opened", "before"]},
                        "target": {"root": "local", "parts": ["before"]},
                    },
                    {
                        "path": {"root": "state", "parts": ["clicked", "after"]},
                        "target": {"root": "local", "parts": ["after"]},
                    },
                ],
                "output": [
                    {
                        "source": {"root": "local", "parts": []},
                        "target": {"root": "state", "parts": ["result"]},
                    }
                ],
            },
        ],
        "edges": [
            {"from": "open", "outcome": "ok", "to": "wait"},
            {"from": "wait", "outcome": "ok", "to": "collect"},
            {"from": "collect", "outcome": "ok", "to": "__end__"},
        ],
        "output": [
            {
                "path": {"root": "state", "parts": ["result", "before"]},
                "target": {"root": "local", "parts": ["before"]},
            },
            {
                "path": {"root": "state", "parts": ["result", "after"]},
                "target": {"root": "local", "parts": ["after"]},
            },
            {
                "path": {"root": "state", "parts": ["result", "closed"]},
                "target": {"root": "local", "parts": ["closed"]},
            },
        ],
    }

    await server.api.create_artifact_from_plan(
        artifact_id="browser_click_case_study",
        version=1,
        title="Browser Click Case Study",
        plan=plan,
        outcomes=["ok"],
        source_bindings={"local.browser_click": "local.browser_click"},
    )
    await server.api.save_deployment(
        {
            "id": "browser_click_case_study.default",
            "artifact_id": "browser_click_case_study",
            "artifact_version": 1,
            "bindings": {"local.browser_click": "local.browser_click"},
        }
    )
    run = await server.api.run_deployment(
        deployment_id="browser_click_case_study.default",
        workflow_input={
            "button_label": "Launch Workflow",
            "open_browser": False,
            "simulate": True,
            "timeout_seconds": 2,
        },
    )

    assert run["status"] == "completed"
    assert run["output"]["before"]["clicked"] is False
    assert run["output"]["after"]["clicked"] is True
    assert run["output"]["after"]["status_text"] == "Button clicked"
    assert run["output"]["closed"] is True
    assert run["trace_count"] >= 3

