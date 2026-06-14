# Thesis Case Study Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible deterministic report-workflow example and evidence bundle that the thesis/system-design document can cite.

**Architecture:** The example should use a trusted Python source as the deterministic provider and the existing `wf` / `wf-rpc-server` lifecycle as the product surface. The evidence must prove the current code path, not restate claims from docs without verification.

**Tech Stack:** Python 3.14, Pydantic, `wf_authoring.node`, `wf_config`, `wf_server`, JSON-RPC HTTP transport, Typer CLI, pytest, ruff, basedpyright.

---

## Files

- Create: `examples/report_workflow/ops.py` — deterministic Python source with typed report extraction and Markdown rendering capabilities.
- Create: `examples/report_workflow/input.md` — stable fixture input for the case study.
- Create: `examples/report_workflow/wf.config.json` — self-contained server/client config for the example.
- Create: `examples/report_workflow/README.md` — runbook commands and expected result shape.
- Create: `tests/examples/test_report_workflow_example.py` — regression tests proving the example source loads and runs through the workflow API.
- Modify: `docs/add/thesis-outline.md` — link the concrete example as the case-study evidence artifact.
- Modify: `docs/add/diagrams.md` — add or refine the case-study lifecycle diagram if needed.
- Modify: `docs/current_roadmap.md` — mark the thesis case-study evidence bundle completed after implementation.

## Claim Verification Rule

Before writing any evidence claim, verify it against code or tests. Use direct code searches such as:

```powershell
rg 'class WorkflowArtifact|class WorkflowDeployment|class WorkflowRun' src/wf_artifacts -n
rg 'WorkflowSourceProvider|CapabilitySource|PythonSourceConfig' src -n
rg 'build_workflow_server_from_workflow_config|build_local_static_workflow_server' src/wf_server -n
```

For every claim in `README.md`, either point to a command in the runbook, a test in `tests/examples/test_report_workflow_example.py`, or a source file path.

## Task 1: Create the Deterministic Python Source

**Files:**
- Create: `examples/report_workflow/ops.py`
- Create: `examples/report_workflow/input.md`

- [ ] **Step 1: Create fixture input**

Create `examples/report_workflow/input.md` with this exact content:

```md
# Weekly Project Update

Summary:
The workflow platform demo is ready for a deterministic thesis case study. The
team wants a repeatable report that does not depend on remote OAuth, LLM output,
or provider quotas.

Actions:
- Alice | Prepare demo config | Friday
- Bao | Run five agent attempts | Monday
- Casey | Capture trace screenshots | Tuesday

Risks:
- Google Drive MCP quota is too low for regression evidence
- Unbounded provider output can waste tokens

Followups:
- Add optional Markdown renderer
- Compare direct script baseline against workflow lifecycle
```

- [ ] **Step 2: Create `ops.py`**

Create `examples/report_workflow/ops.py` with this exact source:

```python
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from wf_authoring import node


class ReadInput(BaseModel):
    path: str = Field(description="Path to a UTF-8 Markdown notes file.")


class ReadOutput(BaseModel):
    text: str


class ExtractInput(BaseModel):
    text: str


class ActionItem(BaseModel):
    owner: str
    task: str
    due: str


class ReportOutput(BaseModel):
    title: str
    summary: str
    action_items: list[ActionItem]
    risks: list[str]
    followups: list[str]


class MarkdownInput(BaseModel):
    report: ReportOutput


class MarkdownOutput(BaseModel):
    markdown: str


@node(name="read_notes")
def read_notes(payload: ReadInput) -> ReadOutput:
    return ReadOutput(text=Path(payload.path).read_text(encoding="utf-8"))


@node(name="extract_report")
def extract_report(payload: ExtractInput) -> ReportOutput:
    title = ""
    summary_lines: list[str] = []
    actions: list[ActionItem] = []
    risks: list[str] = []
    followups: list[str] = []
    section: str | None = None

    for raw_line in payload.text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("# "):
            title = line.removeprefix("# ").strip()
            continue
        if line.endswith(":"):
            section = line[:-1].lower()
            continue
        if section == "summary":
            summary_lines.append(line)
        elif section == "actions" and line.startswith("- "):
            parts = [part.strip() for part in line.removeprefix("- ").split("|")]
            if len(parts) == 3:
                owner, task, due = parts
                actions.append(ActionItem(owner=owner, task=task, due=due))
        elif section == "risks" and line.startswith("- "):
            risks.append(line.removeprefix("- ").strip())
        elif section == "followups" and line.startswith("- "):
            followups.append(line.removeprefix("- ").strip())

    return ReportOutput(
        title=title,
        summary=" ".join(summary_lines),
        action_items=actions,
        risks=risks,
        followups=followups,
    )


@node(name="render_markdown_report")
def render_markdown_report(payload: MarkdownInput) -> MarkdownOutput:
    report = payload.report
    lines = [
        f"# {report.title}",
        "",
        report.summary,
        "",
        "## Action Items",
    ]
    lines.extend(
        f"- {item.owner}: {item.task} (due: {item.due})"
        for item in report.action_items
    )
    lines.extend(["", "## Risks"])
    lines.extend(f"- {risk}" for risk in report.risks)
    lines.extend(["", "## Followups"])
    lines.extend(f"- {followup}" for followup in report.followups)
    return MarkdownOutput(markdown="\n".join(lines))


registry = [read_notes, extract_report, render_markdown_report]
```

- [ ] **Step 3: Commit the source fixture**

Run:

```powershell
git add examples/report_workflow/input.md examples/report_workflow/ops.py
git commit -m "docs: add deterministic report source fixture"
```

Expected: commit succeeds.

## Task 2: Add Example Workflow Config

**Files:**
- Create: `examples/report_workflow/wf.config.json`

- [ ] **Step 1: Create config**

Create `examples/report_workflow/wf.config.json` with this exact JSON:

```json
{
  "version": 1,
  "client": {
    "target": {
      "kind": "rpc_http",
      "url": "http://127.0.0.1:8771/rpc",
      "timeout_seconds": 30
    }
  },
  "server": {
    "store": {
      "kind": "filesystem",
      "root": ".wf_report_store"
    },
    "transports": [
      {
        "kind": "rpc_http",
        "host": "127.0.0.1",
        "port": 8771,
        "path": "/rpc"
      }
    ],
    "sources": [
      {
        "kind": "python",
        "id": "local.report",
        "path": ".",
        "module": "ops",
        "registry": "registry"
      }
    ]
  }
}
```

- [ ] **Step 2: Validate config manually**

Run from repo root:

```powershell
uv run wf config validate examples/report_workflow/wf.config.json
```

Expected: command exits `0` and reports a valid config. If this command name differs in current code, inspect `uv run wf config --help` and update the runbook to the real command.

- [ ] **Step 3: Commit config**

Run:

```powershell
git add examples/report_workflow/wf.config.json
git commit -m "docs: add report workflow example config"
```

Expected: commit succeeds.

## Task 3: Test the Example Source and Workflow API Path

**Files:**
- Create: `tests/examples/test_report_workflow_example.py`

- [ ] **Step 1: Write tests**

Create `tests/examples/test_report_workflow_example.py` with this exact test module:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from wf_config import load_workflow_config
from wf_server.config import build_workflow_server_from_workflow_config


EXAMPLE_DIR = Path(__file__).resolve().parents[2] / "examples" / "report_workflow"


@pytest.mark.asyncio
async def test_report_workflow_python_source_loads_and_calls_capability(tmp_path) -> None:
    config = load_workflow_config(EXAMPLE_DIR / "wf.config.json")
    config.server.store.root = tmp_path / "store"
    server = build_workflow_server_from_workflow_config(config)

    listed = await server.api.list_capabilities(source="local.report")
    names = {capability["qualified_name"] for capability in listed["capabilities"]}

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
            "properties": {
                "report": {"type": "object", "reducer": "wf.std.replace"}
            },
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
                        "source": {"root": "input", "parts": ["text"]},
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
```

- [ ] **Step 2: Run the tests and inspect failures**

Run:

```powershell
uv run pytest tests/examples/test_report_workflow_example.py -q
```

Expected first run may fail if current APIs use different method names or response fields. Fix only the test calls to match current code; do not weaken the assertions about title/action items/completed run.

- [ ] **Step 3: Run final focused tests**

Run:

```powershell
uv run pytest tests/examples/test_report_workflow_example.py tests/wf_sources_python/test_loader.py tests/wf_server/test_config_composition.py -q
```

Expected: all tests pass.

- [ ] **Step 4: Commit tests**

Run:

```powershell
git add tests/examples/test_report_workflow_example.py
git commit -m "test: prove report workflow example"
```

Expected: commit succeeds.

## Task 4: Write the Case Study Runbook

**Files:**
- Create: `examples/report_workflow/README.md`
- Modify: `docs/add/thesis-outline.md`
- Modify: `docs/current_roadmap.md`

- [ ] **Step 1: Create README**

Create `examples/report_workflow/README.md` with this content:

```md
# Report Workflow Example

This example is the deterministic thesis case study. It demonstrates a trusted
Python source that turns project notes into a typed report object without using
remote OAuth, LLM calls, or provider quota.

## Files

- `input.md` — fixture notes.
- `ops.py` — Python source exposing `read_notes`, `extract_report`, and
  `render_markdown_report`.
- `wf.config.json` — local server/client config using the `local.report` Python
  source.

## Run

From the repository root:

```powershell
uv run wf config validate examples/report_workflow/wf.config.json
uv run wf-rpc-server --config examples/report_workflow/wf.config.json
```

In another terminal:

```powershell
uv run wf --config examples/report_workflow/wf.config.json status
uv run wf --config examples/report_workflow/wf.config.json cap list --source local.report
uv run wf --config examples/report_workflow/wf.config.json cap call local.report.extract_report --input "{\"text\":\"$(Get-Content examples/report_workflow/input.md -Raw)\"}" --format compact
```

The expected report includes:

- title: `Weekly Project Update`
- three action items
- at least one risk mentioning Google Drive MCP quota
- followups for Markdown rendering and baseline comparison

## Thesis Evidence

The example supports these claims:

- Python sources can expose typed capabilities through the same workflow surface
  as built-in and MCP sources.
- The case-study path is deterministic and does not depend on an LLM or remote
  provider.
- The workflow lifecycle can be exercised through config validation, capability
  inventory, capability calls, artifacts, deployments, runs, inspect, and trace.
```

- [ ] **Step 2: Link from thesis outline**

In `docs/add/thesis-outline.md`, ensure the case-study paragraph names
`examples/report_workflow/README.md` as the runnable evidence bundle.

- [ ] **Step 3: Update roadmap**

In `docs/current_roadmap.md`, add one completed bullet under the thesis/docs area:

```md
- Completed thesis case-study evidence bundle: `examples/report_workflow/`
  provides a deterministic report workflow with Python source, fixture input,
  config, runbook, and tests.
```

- [ ] **Step 4: Run docs smoke**

Run:

```powershell
uv run pytest tests/docs tests/examples/test_report_workflow_example.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit docs**

Run:

```powershell
git add examples/report_workflow/README.md docs/add/thesis-outline.md docs/current_roadmap.md
git commit -m "docs: document report workflow case study"
```

Expected: commit succeeds.

## Task 5: Final Verification

**Files:**
- Verify all changed files.

- [ ] **Step 1: Run focused tests**

Run:

```powershell
uv run pytest tests/examples/test_report_workflow_example.py tests/docs -q
```

Expected: pass.

- [ ] **Step 2: Run lint**

Run:

```powershell
uv run ruff check examples/report_workflow tests/examples
```

Expected: `All checks passed!`

- [ ] **Step 3: Run typecheck**

Run:

```powershell
uv run basedpyright --level error examples/report_workflow tests/examples
```

Expected: `0 errors`.

- [ ] **Step 4: Run whitespace check**

Run:

```powershell
git diff --check
```

Expected: no whitespace errors. CRLF warnings on Windows are acceptable.

- [ ] **Step 5: Move this plan after completion**

After all tasks are implemented and committed, move this plan to:

```text
docs/historical/superpowers/plans/2026-06-14-thesis-case-study-evidence.md
```

Then commit:

```powershell
git add docs/superpowers/plans/2026-06-14-thesis-case-study-evidence.md docs/historical/superpowers/plans/2026-06-14-thesis-case-study-evidence.md
git commit -m "docs: archive thesis case study plan"
```

## Self-Review Checklist

- The example is deterministic and local-first.
- The test proves both capability call and workflow run paths.
- The runbook avoids Google Drive MCP, remote OAuth, and LLM calls as required evidence.
- Every thesis claim in the README points to a command, test, or source file.
- No `wf.std=wf.std` platform-source self-binding appears in new current docs or tests.
