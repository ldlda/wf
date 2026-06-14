from __future__ import annotations

from pathlib import Path

import pytest

from examples.report_workflow.ops import (
    ActionItem,
    ExtractInput,
    MarkdownInput,
    ReadInput,
    ReportOutput,
    _extract_report,
    _read_notes,
    _render_markdown_report,
)
from wf_config import load_workflow_config
from wf_server.config import build_workflow_server_from_workflow_config

EXAMPLE_DIR = Path(__file__).resolve().parents[2] / "examples" / "report_workflow"


def test_report_workflow_read_notes_rejects_paths_outside_example() -> None:
    with pytest.raises(ValueError, match="inside the example"):
        _read_notes(ReadInput(path="../pyproject.toml"))


def test_report_workflow_markdown_renderer_round_trips_through_extractor() -> None:
    report = ReportOutput(
        title="Weekly Project Update",
        summary="Demo summary.",
        action_items=[
            ActionItem(owner="Alice", task="Prepare demo config", due="Friday")
        ],
        risks=["Quota is low"],
        followups=["Render Markdown"],
    )

    rendered = _render_markdown_report(MarkdownInput(report=report))
    extracted = _extract_report(ExtractInput(text=rendered.markdown))

    assert extracted == report


@pytest.mark.asyncio
async def test_report_workflow_python_source_loads_and_calls_capability(
    tmp_path,
) -> None:
    config = load_workflow_config(EXAMPLE_DIR / "wf.config.json")
    config.server.store.root = tmp_path / "store"
    server = build_workflow_server_from_workflow_config(config)

    listed = await server.api.list_capabilities(source_id="local.report")
    names = {capability["name"] for capability in listed["capabilities"]}

    assert "local.report.extract_report" in names

    result = await server.api.call_capability(
        qualified_name="local.report.extract_report",
        payload={"text": (EXAMPLE_DIR / "input.md").read_text(encoding="utf-8")},
    )

    assert result["outcome"] == "ok"
    assert result["output"]["title"] == "Weekly Project Update"
    assert result["output"]["action_items"][0] == {
        "owner": "Alice",
        "task": "Prepare demo config",
        "due": "Friday",
    }
    assert "Google Drive MCP quota" in result["output"]["risks"][0]


@pytest.mark.asyncio
async def test_report_workflow_artifact_deployment_run_path(tmp_path) -> None:
    config = load_workflow_config(EXAMPLE_DIR / "wf.config.json")
    config.server.store.root = tmp_path / "store"
    server = build_workflow_server_from_workflow_config(config)

    plan = {
        "name": "report_case_study",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        "state_schema": {
            "type": "object",
            "properties": {"report": {"type": "object", "reducer": "wf.std.replace"}},
        },
        "output_schema": {
            "type": "object",
            "properties": {"report": {"type": "object"}},
            "required": ["report"],
        },
        "outcomes": ["ok"],
        "start": "extract",
        "nodes": [
            {
                "id": "extract",
                "type": "node",
                "node": "local.report.extract_report",
                "input": [
                    {
                        "path": {"root": "input", "parts": ["text"]},
                        "target": {"root": "local", "parts": ["text"]},
                    }
                ],
                "output": [
                    {
                        "source": {"root": "local", "parts": []},
                        "target": {"root": "state", "parts": ["report"]},
                    }
                ],
            }
        ],
        "edges": [{"from": "extract", "outcome": "ok", "to": "__end__"}],
        "output": [
            {
                "path": {"root": "state", "parts": ["report"]},
                "target": {"root": "local", "parts": ["report"]},
            }
        ],
    }

    await server.api.create_artifact_from_plan(
        artifact_id="report_case_study",
        version=1,
        title="Report Case Study",
        plan=plan,
        outcomes=["ok"],
        source_bindings={"local.report": "local.report"},
    )
    await server.api.save_deployment(
        {
            "id": "report_case_study.default",
            "artifact_id": "report_case_study",
            "artifact_version": 1,
            "bindings": {"local.report": "local.report"},
        }
    )
    run = await server.api.run_deployment(
        deployment_id="report_case_study.default",
        workflow_input={"text": (EXAMPLE_DIR / "input.md").read_text(encoding="utf-8")},
    )

    assert run["status"] == "completed"
    assert run["output"]["report"]["title"] == "Weekly Project Update"
    assert len(run["output"]["report"]["action_items"]) == 3
