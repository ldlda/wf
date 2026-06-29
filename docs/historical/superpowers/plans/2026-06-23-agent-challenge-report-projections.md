# Agent Challenge Report Projections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate equivalent bounded Markdown and JSON reports for every V2 trial and regenerate both after audit without mutating raw evidence.

**Architecture:** Add strict Pydantic report DTOs, project one `TrialReport` to Markdown and JSON, wire projection generation after raw result persistence, and make V2 audit rebuild both. Preserve referenced V1 behavior.

**Tech Stack:** Python 3.14, Pydantic v2, PyYAML, pathlib, argparse, pytest, Ruff, basedpyright.

---

## File Structure

- Create `examples/agent_challenges/report_models.py`.
- Modify `examples/agent_challenges/reports.py`, `runner.py`, `run_trials.py`, `audit.py`, and `base-prompt.md`.
- Create `tests/examples/test_agent_challenge_reports.py`.
- Modify `tests/examples/test_agent_challenge_harness_v2.py`.
- Update `docs/current_roadmap.md` and archive this plan.

### Task 1: Define The Normalized Report

**Files:**
- Create: `examples/agent_challenges/report_models.py`
- Modify: `examples/agent_challenges/reports.py`
- Create: `tests/examples/test_agent_challenge_reports.py`

- [x] **Step 1: Write a failing bounded-report test**

Build a `_raw_result(tmp_path)` fixture matching the current V2 result shape,
including explicit paths, identity, challenge report, parsed text, metrics,
policy, tool calls, and deliberately large stdout/output previews.

```python
def test_trial_report_is_bounded_machine_projection(tmp_path: Path) -> None:
    payload = build_trial_report(_raw_result(tmp_path), audit=None).model_dump(
        mode="json"
    )
    assert payload["schema_version"] == 1
    assert payload["identity"]["challenge_id"] == "fixture"
    assert payload["outcome"]["task_outcome"] == "success"
    assert payload["commands_and_tools"][0]["detail"].endswith(
        "workflow.plan.json"
    )
    serialized = json.dumps(payload)
    assert "large raw stream" not in serialized
    assert "full tool output" not in serialized
    assert payload["manual_audit"]["status"] == "pending"
```

- [x] **Step 2: Run and verify import failure**

```powershell
uv run pytest tests/examples/test_agent_challenge_reports.py::test_trial_report_is_bounded_machine_projection -q
```

- [x] **Step 3: Implement strict DTOs**

Create `TrialIdentity`, `TrialOutcome`, `CommandToolBrief`, `TokenSummary`,
`AutomaticEvidence`, `ManualAuditSummary`, and `TrialReport` using
`ConfigDict(extra="forbid")`.

```python
class StrictReportModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TrialIdentity(StrictReportModel):
    challenge_id: str
    model: str
    variant: str
    instruction_profile: str
    trial_index: int
    repository_commit: str | None = None
    repository_dirty: bool | None = None
    prompt_hashes: dict[str, str] = Field(default_factory=dict)
    raw_result_path: str
    workspace_path: str


class TrialOutcome(StrictReportModel):
    task_outcome: str
    evaluation_validity: str
    duration_seconds: float
    returncode: int | None
    assertion_failures: list[str] = Field(default_factory=list)
    parse_errors: dict[str, dict[str, str]] = Field(default_factory=dict)


class CommandToolBrief(StrictReportModel):
    ordinal: int
    tool: str
    status: str
    title: str
    detail: str | None = None
    failed: bool
    output_chars: int
    output_sha256: str


class TokenSummary(StrictReportModel):
    total: int = 0
    input: int = 0
    output: int = 0
    reasoning: int = 0
    cache_read: int = 0
    cache_write: int = 0


class AutomaticEvidence(StrictReportModel):
    step_count: int = 0
    tool_call_count: int = 0
    failed_tool_call_count: int = 0
    tool_counts: dict[str, int] = Field(default_factory=dict)
    tokens: TokenSummary = Field(default_factory=TokenSummary)
    cost: float = 0.0
    unknown_event_count: int = 0
    reads_by_category: dict[str, list[str]] = Field(default_factory=dict)
    escalated_to_product_code: bool = False
    disallowed_reads: list[str] = Field(default_factory=list)
    opaque_shell_commands: list[str] = Field(default_factory=list)


class ManualAuditSummary(StrictReportModel):
    status: Literal["pending", "complete"] = "pending"
    official_outcome: str | None = None
    auditor: str | None = None
    audited_at: str | None = None
    corrections: list[str] = Field(default_factory=list)
    notes: str = ""
    read_flags: dict[str, bool] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)


class TrialReport(StrictReportModel):
    schema_version: Literal[1] = 1
    identity: TrialIdentity
    outcome: TrialOutcome
    agent_self_report: dict[str, Any] | None = None
    final_agent_answer: str | None = None
    commands_and_tools: list[CommandToolBrief] = Field(default_factory=list)
    automatic_evidence: AutomaticEvidence
    policy_findings: list[str] = Field(default_factory=list)
    self_report_discrepancies: list[str] = Field(default_factory=list)
    manual_audit: ManualAuditSummary = Field(default_factory=ManualAuditSummary)
    follow_up_notes: list[str] = Field(default_factory=list)
```

Identity holds challenge/model/variant/profile/index, repository provenance,
prompt hashes, raw path, and workspace path. Outcome holds task outcome,
validity, duration, return code, assertions, and parser errors. Evidence holds
bounded metrics, read categories, disallowed reads, and opaque commands.

- [x] **Step 4: Implement the builder**

```python
def build_trial_report(
    result: dict[str, object],
    *,
    audit: dict[str, object] | None,
) -> TrialReport:
    """Project immutable raw evidence and optional audit into one report."""
```

Use focused helpers. Require explicit paths; bound final text to 8,000 chars and
command detail to 1,000; retain only tool ordinal/name/status/title/detail,
failure, output size/hash; exclude stdout/stderr/previews/metadata/full input.
Flag observable self-report conflicts. Treat example reads plus
`existing_solution=false` as a manual follow-up, not automatic guilt.

- [x] **Step 5: Verify and commit**

```powershell
uv run pytest tests/examples/test_agent_challenge_reports.py -q
git add examples/agent_challenges/report_models.py examples/agent_challenges/reports.py tests/examples/test_agent_challenge_reports.py
git commit -m "feat: add normalized agent trial report model"
```

### Task 2: Render And Write Both Projections

**Files:**
- Modify: `examples/agent_challenges/reports.py`
- Modify: `tests/examples/test_agent_challenge_reports.py`

- [x] **Step 1: Add failing projection tests**

Assert writes to `workspace/final-report.md` and `results/trial.report.json`,
stable heading order, bounded commands, no raw outputs, pending audit, valid
JSON, and no temporary-file residue.

- [x] **Step 2: Run and verify missing APIs**

```powershell
uv run pytest tests/examples/test_agent_challenge_reports.py -k projection -q
```

- [x] **Step 3: Implement Markdown renderer**

Use exactly these headings:

```markdown
# Trial Report
## Outcome
## Agent Self-Report
## Commands And Tool Calls
## Automatic Evidence
## Policy Findings
## Self-Report Discrepancies
## Manual Audit
## Follow-Up Notes
```

Render empty sections explicitly and commands as ordered bounded entries.

- [x] **Step 4: Implement atomic writes**

```python
@dataclass(frozen=True, slots=True)
class TrialReportPaths:
    markdown: Path
    machine: Path


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def write_trial_report_projections(
    report: TrialReport,
    *,
    markdown_path: Path,
    machine_path: Path,
) -> TrialReportPaths:
    machine = json.dumps(
        report.model_dump(mode="json"), indent=2, sort_keys=True
    ) + "\n"
    markdown = render_trial_report_markdown(report).rstrip() + "\n"
    _atomic_write_text(machine_path, machine)
    _atomic_write_text(markdown_path, markdown)
    return TrialReportPaths(markdown=markdown_path, machine=machine_path)
```

- [x] **Step 5: Verify and commit**

```powershell
uv run pytest tests/examples/test_agent_challenge_reports.py -q
git add examples/agent_challenges/reports.py tests/examples/test_agent_challenge_reports.py
git commit -m "feat: write human and machine trial reports"
```

### Task 3: Generate Reports From The Runner

**Files:**
- Modify: `examples/agent_challenges/runner.py`
- Modify: `examples/agent_challenges/run_trials.py`
- Modify: `tests/examples/test_agent_challenge_harness_v2.py`

- [x] **Step 1: Extend runner integration tests**

For success and timeout, assert explicit `workspace_path`, `result_path`, and
`report_paths`; raw, Markdown, and machine files exist; machine challenge id is
correct; Markdown contains the final answer.

- [x] **Step 2: Run and verify failure**

```powershell
uv run pytest tests/examples/test_agent_challenge_harness_v2.py -k "runner_to_report or timeout" -q
```

- [x] **Step 3: Add explicit paths before the single raw write**

```python
"challenge_id": challenge.manifest.id,
"workspace_path": str(workspace.root.resolve()),
"result_path": str(result_path.resolve()),
"report_paths": {
    "markdown": str((workspace.root / "final-report.md").resolve()),
    "machine": str(result_path.with_suffix(".report.json").resolve()),
},
```

Include `reads_by_category` in policy. Write raw result once before projection
generation; never rewrite it.

- [x] **Step 4: Generate pending-audit projections**

Call `build_trial_report(result, audit=None)` and
`write_trial_report_projections`. On failure preserve raw evidence and return a
concise `report_generation_error`.

- [x] **Step 5: Print report paths**

Add `result_path` and `report_paths` to each central-runner summary.

- [x] **Step 6: Verify and commit**

```powershell
uv run pytest tests/examples/test_agent_challenge_harness_v2.py -k "runner or timeout" -q
git add examples/agent_challenges/runner.py examples/agent_challenges/run_trials.py tests/examples/test_agent_challenge_harness_v2.py
git commit -m "feat: generate reports after agent trials"
```

### Task 4: Regenerate Reports After Manual Audit

**Files:**
- Modify: `examples/agent_challenges/audit.py`
- Modify: `examples/agent_challenges/save_manual_audit.py`
- Modify: `tests/examples/test_agent_challenge_reports.py`

- [x] **Step 1: Add failing regeneration test**

```python
paths = save_v2_manual_audit(
    result_path,
    official_outcome="pass",
    auditor="reviewer",
    audited_at="2026-06-23T00:00:00Z",
    read_overrides={"existing_solution": True},
    corrections=["Agent inspected a ready-made workflow plan."],
    notes="Technical run passed; self-report corrected.",
)
```

Assert YAML, JSON, and Markdown contain the official grade/corrections.

- [x] **Step 2: Add invalid-audit preservation test**

Use outcome `maybe`, expect `ValueError`, and assert previous projections remain
byte-for-byte unchanged.

- [x] **Step 3: Run and verify missing API**

```powershell
uv run pytest tests/examples/test_agent_challenge_reports.py -k "manual_audit or invalid" -q
```

- [x] **Step 4: Implement V2 audit writer**

Add:

```python
@dataclass(frozen=True, slots=True)
class V2AuditPaths:
    audit: Path
    markdown: Path
    machine: Path


def save_v2_manual_audit(
    result_path: Path,
    *,
    official_outcome: str,
    auditor: str = "human",
    audited_at: str | None = None,
    read_overrides: dict[str, bool] | None = None,
    evidence_overrides: dict[str, object] | None = None,
    corrections: list[str] | None = None,
    notes: str = "",
) -> V2AuditPaths:
    """Write authoritative audit data and regenerate both report projections."""
```

Allow only `pass`, `fail`, `invalid`; require V2; use explicit raw paths;
validate before writes; atomically write audit; rebuild both projections; never
rewrite raw result.

- [x] **Step 5: Route existing CLI by harness version**

For V2, interpret `--manual-classification` as official outcome, reject
`--from-report`, and print JSON containing all three paths. Preserve referenced
V1 behavior.

- [x] **Step 6: Verify and commit**

```powershell
uv run pytest tests/examples/test_agent_challenge_reports.py -q
uv run python examples/agent_challenges/save_manual_audit.py --help
git add examples/agent_challenges/audit.py examples/agent_challenges/save_manual_audit.py tests/examples/test_agent_challenge_reports.py
git commit -m "feat: regenerate trial reports after audit"
```

### Task 5: Clarify Shared Self-Reporting Rules

**Files:**
- Modify: `examples/agent_challenges/base-prompt.md`
- Modify: `tests/examples/test_agent_challenge_harness_v2.py`

- [x] **Step 1: Add failing assertions**

Assert the prompt mentions `tests/`, `examples/`, `read.product_code: true`,
`read.existing_solution: true`, and `read.adjacent_attempts: true`.

- [x] **Step 2: Add approved paragraph**

```markdown
Files under `tests/` and `examples/` may contain complete or partial solutions.
If you inspect them, report `read.product_code: true`; also report
`read.existing_solution: true` when they provide a ready-made solution, or
`read.adjacent_attempts: true` when they contain prior trial outputs.
```

- [x] **Step 3: Verify and commit**

```powershell
uv run pytest tests/examples/test_agent_challenge_harness_v2.py -k base_prompt -q
git add examples/agent_challenges/base-prompt.md tests/examples/test_agent_challenge_harness_v2.py
git commit -m "docs: clarify challenge self-report rules"
```

### Task 6: Final Verification And Documentation

**Files:**
- Modify: `docs/current_roadmap.md`
- Move this plan to `docs/historical/superpowers/plans/`.

- [x] **Step 1: Run verification**

```powershell
uv run pytest tests/examples/test_agent_challenge_reports.py tests/examples/test_agent_challenge_harness_v2.py tests/examples/test_agent_challenge_skill_bundle.py tests/examples/test_opencode_browser_click_challenge.py tests/examples/test_report_workflow_challenge.py -q
uv run ruff check examples/agent_challenges tests/examples/test_agent_challenge_reports.py tests/examples/test_agent_challenge_harness_v2.py
uv run ruff format --check examples/agent_challenges tests/examples/test_agent_challenge_reports.py tests/examples/test_agent_challenge_harness_v2.py
uv run basedpyright --level error examples/agent_challenges tests/examples/test_agent_challenge_reports.py tests/examples/test_agent_challenge_harness_v2.py
git diff --check
```

- [x] **Step 2: Smoke CLI help**

```powershell
uv run python examples/agent_challenges/run_trials.py --help
uv run python examples/agent_challenges/save_manual_audit.py --help
```

- [x] **Step 3: Update roadmap and archive**

Record completion, then move this plan to
`docs/historical/superpowers/plans/2026-06-23-agent-challenge-report-projections.md`.

- [x] **Step 4: Review boundaries**

Confirm raw result is written once, machine report excludes raw outputs,
Markdown headings are stable, explicit paths are used, audit regenerates both,
V1 remains intact, and no runbook/branching challenge leaked into this slice.

- [x] **Step 5: Commit completion docs**

```powershell
git add docs/current_roadmap.md docs/superpowers/plans/2026-06-23-agent-challenge-report-projections.md docs/historical/superpowers/plans/2026-06-23-agent-challenge-report-projections.md
git commit -m "docs: record agent challenge report projections"
```
