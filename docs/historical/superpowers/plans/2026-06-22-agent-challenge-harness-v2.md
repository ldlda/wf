# Agent Challenge Harness V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a manifest-driven generic challenge runner with layered prompts, `none|skills|all` instruction profiles, one-hour trial ceilings, normalized OpenCode tool/token evidence, policy findings, and generated audit reports.

**Architecture:** Challenge manifests and templates are data; executable code lives in `examples/agent_challenges`. The runner creates one isolated trial workspace, composes base/profile/challenge prompts, executes OpenCode from that workspace, preserves raw JSONL, and delegates bounded normalization to focused metrics/policy/report modules. Automatic task classification and validity are provisional; manual audit remains authoritative.

**Tech Stack:** Python 3.14, dataclasses/Pydantic, PyYAML, subprocess, hashlib, pytest, existing OpenCode JSONL format.

---

## File Structure

- Create `examples/agent_challenges/models.py`: manifest/profile/result DTOs.
- Create `examples/agent_challenges/manifests.py`: YAML loading and path resolution.
- Create `examples/agent_challenges/prompts.py`: layered prompt rendering/provenance.
- Create `examples/agent_challenges/metrics.py`: JSONL event/tool/token normalization.
- Create `examples/agent_challenges/policy.py`: observed path categorization and validity.
- Modify `examples/agent_challenges/workspace.py`: profile-aware workspace creation and
  instruction bundle copying.
- Modify `examples/agent_challenges/opencode_io.py`: command uses persisted rendered prompt.
- Modify `examples/agent_challenges/runner.py`: manifest/profile orchestration, trial cwd,
  3,600-second default, normalized evidence.
- Modify `examples/agent_challenges/reports.py`: generated report with evidence sections.
- Modify `examples/agent_challenges/audit.py`: consume v2 task/validity fields.
- Create `examples/agent_challenges/run_trials.py`: central CLI.
- Create `examples/agent_challenges/save_trial_report.py`: central report CLI.
- Create `examples/agent_challenges/save_manual_audit.py`: central audit CLI.
- Create `examples/agent_challenges/base-prompt.md`: invariant benchmark rules.
- Create `examples/agent_challenges/profile-prompts/{none,skills,all}.md`: policy fragments.
- Create `tests/examples/test_agent_challenge_harness_v2.py`: generic behavior tests.

### Task 1: Define Manifest And Profile Models

**Files:**
- Create: `examples/agent_challenges/models.py`
- Create: `examples/agent_challenges/manifests.py`
- Create: `tests/examples/test_agent_challenge_harness_v2.py`

- [ ] **Step 1: Write failing manifest/profile tests**

Create `tests/examples/test_agent_challenge_harness_v2.py` with imports and:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from examples.agent_challenges.manifests import load_challenge_manifest
from examples.agent_challenges.models import InstructionProfile


def _write_manifest(root: Path) -> Path:
    (root / "workspace_template").mkdir(parents=True)
    (root / "challenge-prompt.md").write_text("Build it.\n", encoding="utf-8")
    path = root / "challenge.yaml"
    path.write_text(
        """\
version: 1
id: fixture
prompt: challenge-prompt.md
workspace_template: workspace_template
source:
  id: local.fixture
  root: source
  module: ops
  registry: registry
store_root: .wf_fixture_store
server:
  config: wf.config.json
  default_port: 8779
report:
  required_fields: [value, run_failed]
  success_assertions:
    value: expected
    run_failed: false
""",
        encoding="utf-8",
    )
    return path


def test_load_challenge_manifest_resolves_paths(tmp_path: Path) -> None:
    manifest_path = _write_manifest(tmp_path)

    loaded = load_challenge_manifest(manifest_path)

    assert loaded.manifest.id == "fixture"
    assert loaded.root == tmp_path.resolve()
    assert loaded.prompt_path == (tmp_path / "challenge-prompt.md").resolve()
    assert loaded.workspace_template == (tmp_path / "workspace_template").resolve()
    assert loaded.manifest.report.success_assertions == {
        "value": "expected",
        "run_failed": False,
    }


def test_instruction_profiles_are_exactly_the_supported_conditions() -> None:
    assert [profile.value for profile in InstructionProfile] == [
        "none",
        "skills",
        "all",
    ]


def test_invalid_manifest_rejects_parent_traversal(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path)
    text = path.read_text(encoding="utf-8").replace(
        "workspace_template: workspace_template",
        "workspace_template: ../outside",
    )
    path.write_text(text, encoding="utf-8")

    with pytest.raises(ValueError, match="workspace_template"):
        load_challenge_manifest(path)
```

- [ ] **Step 2: Run tests and verify imports fail**

```powershell
uv run pytest tests/examples/test_agent_challenge_harness_v2.py -q
```

Expected: import failures for `models`/`manifests`.

- [ ] **Step 3: Implement Pydantic manifest DTOs**

Create `examples/agent_challenges/models.py`:

```python
from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class InstructionProfile(StrEnum):
    NONE = "none"
    SKILLS = "skills"
    ALL = "all"


class SourceManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    root: str = Field(min_length=1)
    module: str = Field(min_length=1)
    registry: str = Field(min_length=1)


class ServerManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    config: str = Field(min_length=1)
    default_port: int = Field(ge=1, le=65535)


class ReportManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    required_fields: list[str] = Field(default_factory=list)
    success_assertions: dict[str, Any] = Field(default_factory=dict)


class ChallengeManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    prompt: str
    workspace_template: str
    source: SourceManifest
    store_root: str
    server: ServerManifest
    report: ReportManifest


class LoadedChallenge(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    manifest_path: Path
    root: Path
    prompt_path: Path
    workspace_template: Path
    source_root: Path
    server_config: Path
    manifest: ChallengeManifest
```

- [ ] **Step 4: Implement safe manifest loading**

Create `examples/agent_challenges/manifests.py`:

```python
from __future__ import annotations

from pathlib import Path

import yaml

from .models import ChallengeManifest, LoadedChallenge


def _inside(root: Path, relative: str, *, field: str) -> Path:
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError(f"challenge {field} must stay inside challenge directory")
    return candidate


def load_challenge_manifest(path: Path) -> LoadedChallenge:
    manifest_path = path.resolve()
    root = manifest_path.parent
    loaded = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest = ChallengeManifest.model_validate(loaded)
    prompt_path = _inside(root, manifest.prompt, field="prompt")
    workspace_template = _inside(
        root, manifest.workspace_template, field="workspace_template"
    )
    source_root = (root / manifest.source.root).resolve()
    server_config = (root / manifest.server.config).resolve()
    if not prompt_path.is_file():
        raise ValueError(f"challenge prompt does not exist: {prompt_path}")
    if not workspace_template.is_dir():
        raise ValueError(f"challenge workspace_template does not exist: {workspace_template}")
    return LoadedChallenge(
        manifest_path=manifest_path,
        root=root,
        prompt_path=prompt_path,
        workspace_template=workspace_template,
        source_root=source_root,
        server_config=server_config,
        manifest=manifest,
    )
```

- [ ] **Step 5: Run manifest tests and commit**

```powershell
uv run pytest tests/examples/test_agent_challenge_harness_v2.py -q
git add examples/agent_challenges/models.py examples/agent_challenges/manifests.py tests/examples/test_agent_challenge_harness_v2.py
git commit -m "feat: add agent challenge manifests"
```

### Task 2: Add Layered Prompts And Profile-Aware Workspaces

**Files:**
- Create: `examples/agent_challenges/base-prompt.md`
- Create: `examples/agent_challenges/profile-prompts/none.md`
- Create: `examples/agent_challenges/profile-prompts/skills.md`
- Create: `examples/agent_challenges/profile-prompts/all.md`
- Create: `examples/agent_challenges/prompts.py`
- Modify: `examples/agent_challenges/workspace.py`
- Test: `tests/examples/test_agent_challenge_harness_v2.py`

- [ ] **Step 1: Add failing prompt/profile tests**

Append tests that call `compose_trial_prompt` and `prepare_v2_trial_workspace`:

```python
from examples.agent_challenges.prompts import compose_trial_prompt
from examples.agent_challenges.workspace import prepare_v2_trial_workspace


def test_challenge_prompt_is_identical_across_profiles(tmp_path: Path) -> None:
    challenge = load_challenge_manifest(_write_manifest(tmp_path / "challenge"))
    rendered = {
        profile: compose_trial_prompt(
            challenge,
            profile=profile,
            wf_command_prefix="uv run wf --config wf.config.json --local",
            server_context="Local mode.",
            workspace_path=tmp_path / profile.value,
        )
        for profile in InstructionProfile
    }

    assert {value.challenge_sha256 for value in rendered.values()} == {
        rendered[InstructionProfile.NONE].challenge_sha256
    }
    assert len({value.rendered_sha256 for value in rendered.values()}) == 3
    assert "report the exact blocker" in rendered[InstructionProfile.NONE].text
    assert ".agent/skills" in rendered[InstructionProfile.SKILLS].text
    assert "inspect broader repository" in rendered[InstructionProfile.ALL].text


def test_skills_profile_copies_bundle_but_none_does_not(tmp_path: Path) -> None:
    challenge = load_challenge_manifest(_write_manifest(tmp_path / "challenge"))
    bundle = ROOT / "examples/agent_challenges/instruction_bundles/workflow_cli.yaml"

    none_workspace = prepare_v2_trial_workspace(
        challenge,
        profile=InstructionProfile.NONE,
        model="model",
        index=1,
        workspaces_dir=tmp_path / "workspaces",
        instruction_bundle=bundle,
    )
    skills_workspace = prepare_v2_trial_workspace(
        challenge,
        profile=InstructionProfile.SKILLS,
        model="model",
        index=2,
        workspaces_dir=tmp_path / "workspaces",
        instruction_bundle=bundle,
    )

    assert not (none_workspace.root / ".agent/skills").exists()
    assert (skills_workspace.root / ".agent/skills/wf-cli/SKILL.md").is_file()
    assert skills_workspace.instruction_files
```

Add `ROOT = Path(__file__).resolve().parents[2]` if it is not already present.

- [ ] **Step 2: Create invariant and profile prompts**

Create `base-prompt.md` with placeholders:

```markdown
# Workflow Agent Challenge

Use the repository's public `wf` product path to complete the challenge below.
Do not replace the workflow lifecycle with a helper script that imports internal
workflow APIs. Preserve exact commands, failures, run ids, and evidence in your
final answer.

Use this command prefix:

    {{wf_command_prefix}}

{{server_context}}

Your writable trial workspace is `{{workspace_path}}`. Write attempt files only
inside it. End with the challenge's requested YAML self-report. The self-report
will be checked against observed tool calls and manually audited.
```

Create profile fragments:

`none.md`:

```markdown
## Instruction Profile: none

Use challenge files, `wf --help`, `wf schema`, validation, inspect, and bounded
trace commands. Do not read repository skills, docs, examples, tests, source,
prior trials, or prior stores. If public surfaces are insufficient, report the
exact blocker and finish the task as failed rather than reverse-engineering the
implementation.
```

`skills.md`:

```markdown
## Instruction Profile: skills

Use the supplied skills under `.agent/skills/` plus public `wf` commands. Do not
read repository examples, tests, source, prior trials, or prior stores. If the
skills and public surfaces are insufficient, report the exact blocker rather
than reverse-engineering implementation code.
```

`all.md`:

```markdown
## Instruction Profile: all

Start with the supplied skills and public docs. If genuinely blocked, you may
inspect broader repository docs, examples, tests, and source. Report what you
read; observed tool calls will also be retained for audit.
```

- [ ] **Step 3: Implement prompt composition and hashes**

Create `prompts.py` with a `RenderedPrompt` frozen dataclass, SHA-256 helper,
placeholder replacement, and concatenation in this order:

```text
base prompt
profile fragment
challenge prompt
```

The dataclass must expose `text`, `base_sha256`, `profile_sha256`,
`challenge_sha256`, and `rendered_sha256`. Reject unresolved `{{...}}`
placeholders with `ValueError`.

- [ ] **Step 4: Extend workspace preparation**

Add a `V2TrialWorkspace` dataclass with:

```python
root: Path
config_path: Path
rendered_prompt_path: Path
instruction_files: tuple[Path, ...]
```

Implement `prepare_v2_trial_workspace` to:

- create the unique workspace;
- copy the challenge template;
- write the local config;
- for `skills` and `all`, load the explicit bundle manifest and `copy2` each
  file under `.agent/skills/<destination>`;
- for `none`, copy no instruction files;
- never use symbolic links or junctions.

- [ ] **Step 5: Run profile tests and commit**

```powershell
uv run pytest tests/examples/test_agent_challenge_harness_v2.py -k "prompt or profile" -q
git add examples/agent_challenges/base-prompt.md examples/agent_challenges/profile-prompts examples/agent_challenges/prompts.py examples/agent_challenges/workspace.py tests/examples/test_agent_challenge_harness_v2.py
git commit -m "feat: add challenge instruction profiles"
```

### Task 3: Normalize OpenCode Tool And Token Events

**Files:**
- Create: `examples/agent_challenges/metrics.py`
- Test: `tests/examples/test_agent_challenge_harness_v2.py`

- [ ] **Step 1: Add a realistic JSONL fixture test**

Append a test using four JSON lines: `step_start`, successful `tool_use` for
`read`, failed `tool_use` for `bash`, and `step_finish` with token/cost data.
Assert:

```python
metrics.step_count == 1
metrics.tool_call_count == 2
metrics.failed_tool_call_count == 1
metrics.tool_counts == {"bash": 1, "read": 1}
metrics.tokens.total == 120
metrics.tokens.input == 20
metrics.tokens.output == 30
metrics.tokens.reasoning == 10
metrics.tokens.cache_read == 60
metrics.cost == 0.01
metrics.tool_calls[0].tool == "read"
metrics.tool_calls[0].output_chars == 4000
len(metrics.tool_calls[0].output_preview) <= 500
```

- [ ] **Step 2: Run and verify the metrics import fails**

```powershell
uv run pytest tests/examples/test_agent_challenge_harness_v2.py -k metrics -q
```

Expected: import failure for `metrics`.

- [ ] **Step 3: Implement event parsing DTOs**

In `metrics.py`, define frozen dataclasses:

```python
TokenMetrics(total, input, output, reasoning, cache_read, cache_write)
ToolCallEvidence(ordinal, call_id, tool, status, title, input, metadata,
                 output_chars, output_preview, output_sha256, failed)
TrialMetrics(step_count, tool_call_count, failed_tool_call_count, tool_counts,
             tokens, cost, unknown_event_count, tool_calls)
```

Implement `extract_trial_metrics(stdout: str, *, preview_chars: int = 500)`:

- parse each nonblank line independently as JSON;
- preserve malformed line count as unknown evidence instead of aborting;
- count `step_finish` events and sum numeric token fields;
- read nested cache `read`/`write` fields;
- sum numeric `cost` values;
- normalize `tool_use.part` and `part.state` fields;
- hash full string output with SHA-256 and store only the bounded preview in
  normalized metrics;
- retain unknown event count.

- [ ] **Step 4: Add JSON serialization helper**

Implement `metrics_payload(metrics: TrialMetrics) -> dict[str, Any]` using
`dataclasses.asdict`, with tool-count keys sorted for deterministic output.

- [ ] **Step 5: Run metrics tests and commit**

```powershell
uv run pytest tests/examples/test_agent_challenge_harness_v2.py -k metrics -q
git add examples/agent_challenges/metrics.py tests/examples/test_agent_challenge_harness_v2.py
git commit -m "feat: extract opencode trial metrics"
```

### Task 4: Derive Policy Evidence From Tool Calls

**Files:**
- Create: `examples/agent_challenges/policy.py`
- Test: `tests/examples/test_agent_challenge_harness_v2.py`

- [ ] **Step 1: Add path-category and validity tests**

Create tool evidence fixtures for reads of:

- current workspace file;
- `.agent/skills/wf-cli/SKILL.md`;
- repository `src/wf_cli/app.py`;
- repository `tests/wf_cli/test_app.py`;
- another trial workspace;
- prior `.wf_*` store;
- opaque `bash` command.

Assert:

- `none` with source read is `contaminated` and records the path;
- `skills` permits copied skill reads but source/test reads contaminate;
- `all` permits source/test reads and sets `escalated_to_product_code=True`
  without contamination;
- opaque shell commands produce `unauditable` only when no stronger
  contamination result exists.

- [ ] **Step 2: Implement policy DTO and categorization**

Create:

```python
class EvaluationValidity(StrEnum):
    CLEAN = "clean"
    CONTAMINATED = "contaminated"
    UNAUDITABLE = "unauditable"

@dataclass(frozen=True, slots=True)
class PolicyEvidence:
    validity: EvaluationValidity
    disallowed_reads: tuple[str, ...]
    escalated_to_product_code: bool
    opaque_shell_commands: tuple[str, ...]
    reads_by_category: dict[str, tuple[str, ...]]
```

Implement `evaluate_policy(profile, tool_calls, *, workspace_root,
repository_root, workspaces_root)` using normalized tool names/inputs.

Recognize structured read/search inputs for tools named `read`, `glob`,
`grep`, `list`, and equivalent names already observed in saved OpenCode output.
Classify resolved paths into workspace, supplied skills, docs, examples, tests,
source, adjacent attempts, prior stores, or outside/unknown.

For shell tools, store the command text. Recognize only clear literal path
arguments; do not claim complete shell parsing. Commands that cannot be
classified remain in `opaque_shell_commands`.

- [ ] **Step 3: Run policy tests and commit**

```powershell
uv run pytest tests/examples/test_agent_challenge_harness_v2.py -k policy -q
git add examples/agent_challenges/policy.py tests/examples/test_agent_challenge_harness_v2.py
git commit -m "feat: derive challenge policy evidence"
```

### Task 5: Integrate Manifest Runner, Workspace CWD, And One-Hour Ceiling

**Files:**
- Modify: `examples/agent_challenges/opencode_io.py`
- Modify: `examples/agent_challenges/runner.py`
- Create: `examples/agent_challenges/run_trials.py`
- Test: `tests/examples/test_agent_challenge_harness_v2.py`

- [ ] **Step 1: Add runner integration tests with injected subprocess**

Add tests that inject a fake run function and assert:

- default timeout is `3600`;
- `cwd` is the generated trial workspace;
- exactly one profile is present in config;
- rendered prompt is persisted;
- result JSON contains `instruction_profile`, prompt hashes, metrics, policy,
  repository commit/dirty marker, and raw stdout/stderr;
- timeout preserves partial stdout and extracted partial metrics.

- [ ] **Step 2: Replace command construction input**

Change `TrialConfig`/`build_opencode_command` so command construction receives
the already-rendered prompt text or reads `rendered_prompt_path`. Prompt
composition must not happen inside `opencode_io.py`.

Keep:

```text
opencode run [--attach URL] <rendered prompt> --format json --model ... --variant ...
```

- [ ] **Step 3: Refactor runner entrypoint**

The central `run_trials.py` CLI accepts:

```text
--challenge PATH
--instruction-profile none|skills|all
--model MODEL
--variant VARIANT
--trials N
--timeout-seconds 3600
--attach URL
--results-dir PATH
--workspaces-dir PATH
--instruction-bundle PATH
--server-url URL
--start-server
--server-port PORT
```

Require one explicit or default profile, never a profile list. Use one generated
workspace per trial and pass that workspace as `cwd` to `subprocess.run`.

- [ ] **Step 4: Write normalized evidence after every terminal path**

For success, nonzero process exit, timeout, and parse error:

- write raw result JSON first;
- extract metrics from available stdout;
- evaluate policy from available tool calls;
- write `metrics.json` in the workspace;
- include prompt/bundle hashes and repository provenance;
- call report generation;
- never discard raw evidence if later stages fail.

- [ ] **Step 5: Run runner tests and direct help smoke**

```powershell
uv run pytest tests/examples/test_agent_challenge_harness_v2.py -k "runner or timeout" -q
uv run python examples/agent_challenges/run_trials.py --help
```

Expected: tests pass and help lists `--instruction-profile` and default timeout.

- [ ] **Step 6: Commit runner integration**

```powershell
git add examples/agent_challenges/opencode_io.py examples/agent_challenges/runner.py examples/agent_challenges/run_trials.py tests/examples/test_agent_challenge_harness_v2.py
git commit -m "feat: run profiled agent challenge trials"
```

### Task 6: Generate Evidence-Rich Reports And Central Audit CLIs

**Files:**
- Modify: `examples/agent_challenges/reports.py`
- Modify: `examples/agent_challenges/audit.py`
- Create: `examples/agent_challenges/save_trial_report.py`
- Create: `examples/agent_challenges/save_manual_audit.py`
- Test: `tests/examples/test_agent_challenge_harness_v2.py`

- [ ] **Step 1: Add report snapshot assertions**

Build a small result payload and assert generated Markdown contains:

```text
Instruction profile: skills
Task outcome: success
Evaluation validity: contaminated
Duration
Observed token metrics
Tool calls by tool
Disallowed reads
Agent self-report discrepancies
Final agent answer
Manual audit: pending
```

Assert full tool outputs are absent and previews are bounded.

- [ ] **Step 2: Separate task outcome from validity in reports**

Update `reports.py` to render these sections in order:

1. Trial identity/provenance.
2. Task outcome and evaluation validity.
3. Duration/token/cost metrics.
4. Tool/command summary.
5. Observed reads and policy findings.
6. Agent self-report and observed discrepancies.
7. Final agent answer.
8. Manual-audit status.

Keep `report_from_result` and `save_report_from_result_payload` as generic
helpers, but remove browser-click assumptions.

- [ ] **Step 3: Update manual audit payload**

`manual-audit.yaml` must include:

```yaml
task_outcome: success
evaluation_validity: clean
official_outcome: pass
auditor_notes: "..."
```

The manual command can override automatic task/validity fields but must retain
the automatic values under `automatic_evidence` for comparison.

- [ ] **Step 4: Add central wrapper CLIs**

`save_trial_report.py` delegates to `reports.main`; `save_manual_audit.py`
delegates to `audit.main`. Both must support direct execution from repo root and
display useful `--help` text.

- [ ] **Step 5: Run report/audit tests and commit**

```powershell
uv run pytest tests/examples/test_agent_challenge_harness_v2.py -k "report or audit" -q
git add examples/agent_challenges/reports.py examples/agent_challenges/audit.py examples/agent_challenges/save_trial_report.py examples/agent_challenges/save_manual_audit.py tests/examples/test_agent_challenge_harness_v2.py
git commit -m "feat: report agent challenge evidence"
```

### Task 7: Final Generic Harness Verification

**Files:**
- Modify: `docs/current_roadmap.md`
- Move after completion: `docs/superpowers/plans/2026-06-22-agent-challenge-harness-v2.md` to `docs/historical/superpowers/plans/2026-06-22-agent-challenge-harness-v2.md`

- [ ] **Step 1: Run focused tests and static checks**

```powershell
uv run pytest tests/examples/test_agent_challenge_harness_v2.py tests/examples/test_agent_challenge_skill_bundle.py -q
uv run ruff check examples/agent_challenges tests/examples/test_agent_challenge_harness_v2.py tests/examples/test_agent_challenge_skill_bundle.py
uv run ruff format --check examples/agent_challenges tests/examples/test_agent_challenge_harness_v2.py tests/examples/test_agent_challenge_skill_bundle.py
uv run basedpyright --level error examples/agent_challenges tests/examples/test_agent_challenge_harness_v2.py tests/examples/test_agent_challenge_skill_bundle.py
git diff --check
```

Expected: all pass; only accepted Windows CRLF warnings may appear.

- [ ] **Step 2: Add roadmap completion note**

```markdown
- Completed: the generic agent challenge harness now supports data-driven
  manifests, layered prompts, explicit `none|skills|all` profiles, one-hour hard
  ceilings, normalized OpenCode tool/token evidence, policy findings, and
  manual-audited reports.
```

- [ ] **Step 3: Archive and commit the plan**

```powershell
New-Item -ItemType Directory -Force docs/historical/superpowers/plans | Out-Null
Move-Item docs/superpowers/plans/2026-06-22-agent-challenge-harness-v2.md docs/historical/superpowers/plans/2026-06-22-agent-challenge-harness-v2.md
git add docs/current_roadmap.md docs/superpowers/plans/2026-06-22-agent-challenge-harness-v2.md docs/historical/superpowers/plans/2026-06-22-agent-challenge-harness-v2.md
git commit -m "docs: record agent challenge harness v2"
```
