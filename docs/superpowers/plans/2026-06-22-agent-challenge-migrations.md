# Agent Challenge Migration And Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate browser-click to the generic data-only harness, remove challenge-local executables, and add a deterministic report-workflow challenge using the same central runner and evidence format.

**Architecture:** Each challenge is a manifest, invariant task prompt, README, workspace template, and ignored result/workspace directories. Browser/report success assertions are declarative and provisional; the central generic classifier/report/audit path owns all execution. No compatibility wrappers remain because they have no production callers.

**Tech Stack:** YAML manifests, Markdown prompts, generic Python challenge harness, pytest.

---

## File Structure

- Create `examples/agent_challenges/browser_click_challenge/challenge.yaml`.
- Move/rewrite `workspace_template/prompt.md` as
  `browser_click_challenge/challenge-prompt.md`.
- Modify `browser_click_challenge/README.md` for central commands/profiles.
- Delete all browser-click `.py` wrappers and package marker.
- Create `examples/agent_challenges/report_workflow_challenge/challenge.yaml`.
- Create `report_workflow_challenge/challenge-prompt.md`.
- Replace/rename `report_workflow_challenge/readme.md` as `README.md`, preserving
  useful user-authored challenge ideas.
- Create `report_workflow_challenge/workspace_template/.gitignore`.
- Create `report_workflow_challenge/results/.gitignore`.
- Create `report_workflow_challenge/workspaces/.gitignore`.
- Rewrite `tests/examples/test_opencode_browser_click_challenge.py` around the
  generic harness and browser manifest.
- Create `tests/examples/test_report_workflow_challenge.py`.
- Modify thesis/evidence docs only after both data-driven challenges are tested.

### Task 1: Convert Browser Click To A Manifest

**Files:**
- Create: `examples/agent_challenges/browser_click_challenge/challenge.yaml`
- Create: `examples/agent_challenges/browser_click_challenge/challenge-prompt.md`
- Modify: `tests/examples/test_opencode_browser_click_challenge.py`

- [ ] **Step 1: Replace wrapper-based manifest tests**

In `tests/examples/test_opencode_browser_click_challenge.py`, replace imports of
`browser_click_challenge.challenge` with:

```python
from examples.agent_challenges.manifests import load_challenge_manifest
from examples.agent_challenges.models import InstructionProfile
from examples.agent_challenges.workspace import prepare_v2_trial_workspace


ROOT = Path(__file__).resolve().parents[2]
BROWSER_CHALLENGE = (
    ROOT
    / "examples"
    / "agent_challenges"
    / "browser_click_challenge"
    / "challenge.yaml"
)
```

Add:

```python
def test_browser_click_manifest_declares_task_success_contract() -> None:
    loaded = load_challenge_manifest(BROWSER_CHALLENGE)

    assert loaded.manifest.id == "browser_click"
    assert loaded.manifest.source.id == "local.browser_click"
    assert loaded.manifest.report.success_assertions == {
        "before_clicked": False,
        "after_clicked": True,
        "run_failed": False,
        "leftover_processes": False,
    }


def test_browser_click_workspace_uses_generic_profile_copy(tmp_path: Path) -> None:
    loaded = load_challenge_manifest(BROWSER_CHALLENGE)
    bundle = ROOT / "examples/agent_challenges/instruction_bundles/workflow_cli.yaml"

    workspace = prepare_v2_trial_workspace(
        loaded,
        profile=InstructionProfile.SKILLS,
        model="opencode/test",
        index=1,
        workspaces_dir=tmp_path,
        instruction_bundle=bundle,
    )

    assert workspace.config_path.is_file()
    assert (workspace.root / ".agent/skills/wf-cli/SKILL.md").is_file()
```

- [ ] **Step 2: Run and verify the manifest is missing**

```powershell
uv run pytest tests/examples/test_opencode_browser_click_challenge.py -k "manifest or generic_profile" -q
```

Expected: fail because `challenge.yaml` is missing.

- [ ] **Step 3: Create browser-click manifest**

```yaml
version: 1
id: browser_click
prompt: challenge-prompt.md
workspace_template: workspace_template
source:
  id: local.browser_click
  root: ../../browser_click_workflow
  module: ops
  registry: registry
store_root: .wf_browser_click_store
server:
  config: ../../browser_click_workflow/wf.config.json
  default_port: 8772
report:
  required_fields:
    - used_product_path
    - used_helper_script
    - workflow_file
    - deployment_id
    - run_id
    - before_clicked
    - after_clicked
    - run_failed
    - leftover_processes
    - read
    - attempts
    - missed_requirements
    - notes
  success_assertions:
    before_clicked: false
    after_clicked: true
    run_failed: false
    leftover_processes: false
```

- [ ] **Step 4: Split task-specific prompt from harness policy**

Create `challenge-prompt.md` by retaining only:

- browser-click task requirements;
- deterministic source location/identity;
- allowed draft/raw authoring paths specific to this task;
- task-specific evidence requirements;
- task-specific YAML fields and reporting meanings.

Remove generic content now owned by base/profile prompts:

- product-path/helper-script policy;
- workspace path placeholder;
- code-read/profile policy;
- prior-attempt contamination policy;
- generic manual-audit explanation.

The prompt must still require `before_clicked`, `after_clicked`,
`leftover_processes`, command/run evidence, and the final YAML block.

- [ ] **Step 5: Run manifest/workspace tests and commit**

```powershell
uv run pytest tests/examples/test_opencode_browser_click_challenge.py -k "manifest or generic_profile" -q
git add examples/agent_challenges/browser_click_challenge/challenge.yaml examples/agent_challenges/browser_click_challenge/challenge-prompt.md tests/examples/test_opencode_browser_click_challenge.py
git commit -m "feat: define browser click challenge manifest"
```

### Task 2: Remove Browser-Local Executables

**Files:**
- Delete: `examples/agent_challenges/browser_click_challenge/__init__.py`
- Delete: `examples/agent_challenges/browser_click_challenge/challenge.py`
- Delete: `examples/agent_challenges/browser_click_challenge/classification.py`
- Delete: `examples/agent_challenges/browser_click_challenge/opencode_io.py`
- Delete: `examples/agent_challenges/browser_click_challenge/reports.py`
- Delete: `examples/agent_challenges/browser_click_challenge/run_opencode_trials.py`
- Delete: `examples/agent_challenges/browser_click_challenge/save_trial_report.py`
- Delete: `examples/agent_challenges/browser_click_challenge/save_manual_audit.py`
- Delete: `examples/agent_challenges/browser_click_challenge/workspace_template/prompt.md`
- Modify: `examples/agent_challenges/browser_click_challenge/README.md`
- Modify: `tests/examples/test_opencode_browser_click_challenge.py`

- [ ] **Step 1: Replace direct-execution wrapper tests**

Delete tests that invoke challenge-local scripts. Add central command tests:

```python
def test_central_runner_accepts_browser_challenge() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "examples/agent_challenges/run_trials.py",
            "--help",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "--challenge" in result.stdout
    assert "--instruction-profile" in result.stdout
```

Keep generic classification/report/audit tests in
`test_agent_challenge_harness_v2.py`; remove duplicate wrapper identity tests.

- [ ] **Step 2: Rewrite README commands**

Document:

```powershell
uv run python examples/agent_challenges/run_trials.py `
  --challenge examples/agent_challenges/browser_click_challenge/challenge.yaml `
  --instruction-profile skills `
  --model opencode/mimo-v2.5-free `
  --variant high `
  --trials 1 `
  --attach http://127.0.0.1:4096
```

Also show `none` and `all` as separate invocations and explain the 3,600-second
hard ceiling.

- [ ] **Step 3: Delete challenge-local Python wrappers**

Use `git rm` for every listed `.py` wrapper and the old copied prompt. Do not
leave compatibility re-exports; there are no production callers.

- [ ] **Step 4: Search for stale wrapper paths**

```powershell
rg -n "browser_click_challenge/(run_opencode_trials|save_trial_report|save_manual_audit)|browser_click_challenge\\.(challenge|classification|reports|opencode_io)" . -g '!docs/historical/**'
```

Expected: no live source/test/docs references.

- [ ] **Step 5: Run browser and generic harness tests**

```powershell
uv run pytest tests/examples/test_opencode_browser_click_challenge.py tests/examples/test_agent_challenge_harness_v2.py -q
```

Expected: pass.

- [ ] **Step 6: Commit wrapper removal**

```powershell
git add examples/agent_challenges/browser_click_challenge tests/examples/test_opencode_browser_click_challenge.py
git commit -m "refactor: centralize browser challenge execution"
```

### Task 3: Add The Report Workflow Challenge

**Files:**
- Create: `examples/agent_challenges/report_workflow_challenge/challenge.yaml`
- Create: `examples/agent_challenges/report_workflow_challenge/challenge-prompt.md`
- Create/rename: `examples/agent_challenges/report_workflow_challenge/README.md`
- Create: `examples/agent_challenges/report_workflow_challenge/workspace_template/.gitignore`
- Create: `examples/agent_challenges/report_workflow_challenge/results/.gitignore`
- Create: `examples/agent_challenges/report_workflow_challenge/workspaces/.gitignore`
- Create: `tests/examples/test_report_workflow_challenge.py`

- [ ] **Step 1: Preserve and normalize the user-authored challenge notes**

Read the existing untracked
`examples/agent_challenges/report_workflow_challenge/readme.md`. Preserve its
intended complex report/email/save challenge as future challenge-design notes in
the canonical `README.md`; do not silently delete it. The first executable
challenge remains the deterministic three-node report pipeline so results are
auditable.

- [ ] **Step 2: Write failing report manifest tests**

Create `tests/examples/test_report_workflow_challenge.py`:

```python
from __future__ import annotations

from pathlib import Path

from examples.agent_challenges.manifests import load_challenge_manifest


ROOT = Path(__file__).resolve().parents[2]
REPORT_CHALLENGE = (
    ROOT
    / "examples"
    / "agent_challenges"
    / "report_workflow_challenge"
    / "challenge.yaml"
)


def test_report_workflow_manifest_uses_report_source() -> None:
    loaded = load_challenge_manifest(REPORT_CHALLENGE)

    assert loaded.manifest.id == "report_workflow"
    assert loaded.manifest.source.id == "local.report"
    assert loaded.manifest.report.success_assertions == {
        "title_matches": True,
        "markdown_rendered": True,
        "run_failed": False,
    }
    assert loaded.prompt_path.is_file()
    assert loaded.workspace_template.is_dir()


def test_report_challenge_prompt_requires_full_product_lifecycle() -> None:
    loaded = load_challenge_manifest(REPORT_CHALLENGE)
    prompt = loaded.prompt_path.read_text(encoding="utf-8")

    assert "read_notes" in prompt
    assert "extract_report" in prompt
    assert "render_markdown_report" in prompt
    assert "deployment" in prompt.lower()
    assert "run_id" in prompt
```

- [ ] **Step 3: Run and verify the report manifest is missing**

```powershell
uv run pytest tests/examples/test_report_workflow_challenge.py -q
```

Expected: fail because `challenge.yaml` is missing.

- [ ] **Step 4: Create report challenge manifest**

```yaml
version: 1
id: report_workflow
prompt: challenge-prompt.md
workspace_template: workspace_template
source:
  id: local.report
  root: ../../report_workflow
  module: ops
  registry: registry
store_root: .wf_report_challenge_store
server:
  config: ../../report_workflow/wf.config.json
  default_port: 8773
report:
  required_fields:
    - used_product_path
    - used_helper_script
    - workflow_file
    - deployment_id
    - run_id
    - title_matches
    - markdown_rendered
    - run_failed
    - read
    - attempts
    - missed_requirements
    - notes
  success_assertions:
    title_matches: true
    markdown_rendered: true
    run_failed: false
```

- [ ] **Step 5: Create invariant report challenge prompt**

Require the agent to:

1. discover `local.report` capabilities through public `wf` commands;
2. author a workflow that executes
   `read_notes -> extract_report -> render_markdown_report`;
3. create an artifact and deployment through `wf`;
4. run it against the supplied deterministic input;
5. report the run id and evidence that title equals `Weekly Project Update` and
   Markdown begins with `# Weekly Project Update`;
6. avoid helper scripts that directly drive workflow internals;
7. finish with the manifest-required YAML fields.

Do not include profile policy or implementation-code instructions; the base and
profile prompts own those rules.

- [ ] **Step 6: Create workspace/result directories and README**

Each `.gitignore` should contain:

```gitignore
*
!.gitignore
```

README must show one central runner command per profile and explain that
automatic success is provisional until manual audit.

- [ ] **Step 7: Run report challenge tests and commit**

```powershell
uv run pytest tests/examples/test_report_workflow_challenge.py -q
git add examples/agent_challenges/report_workflow_challenge tests/examples/test_report_workflow_challenge.py
git commit -m "feat: add report workflow agent challenge"
```

### Task 4: Prove Both Challenges Use The Same Harness

**Files:**
- Modify: `tests/examples/test_agent_challenge_harness_v2.py`
- Modify: `docs/add/evidence-index.md`
- Modify: `docs/add/system-design-implementation.md`
- Modify: `docs/current_roadmap.md`
- Move after completion: `docs/superpowers/plans/2026-06-22-agent-challenge-migrations.md` to `docs/historical/superpowers/plans/2026-06-22-agent-challenge-migrations.md`

- [ ] **Step 1: Add parameterized workspace preparation test**

Parameterize browser/report manifest paths and assert both:

- load through the same `load_challenge_manifest`;
- prepare under each profile;
- write a valid local config;
- render profile/challenge prompts;
- produce different challenge hashes but the same base/profile hashes.

- [ ] **Step 2: Run all challenge tests**

```powershell
uv run pytest tests/examples/test_agent_challenge_harness_v2.py tests/examples/test_opencode_browser_click_challenge.py tests/examples/test_report_workflow_challenge.py tests/examples/test_agent_challenge_skill_bundle.py -q
```

Expected: pass.

- [ ] **Step 3: Run static checks**

```powershell
uv run ruff check examples/agent_challenges tests/examples
uv run ruff format --check examples/agent_challenges tests/examples
uv run basedpyright --level error examples/agent_challenges tests/examples
git diff --check
```

Expected: clean except accepted Windows CRLF warnings.

- [ ] **Step 4: Update evidence docs without claiming results**

Document that:

- two data-driven challenges now exist;
- both support `none`, `skills`, and `all` conditions;
- normalized metrics and manual audit are implemented;
- repeated audited model results are still pending and no aggregate success
  claim is made.

- [ ] **Step 5: Archive and commit the plan**

```powershell
New-Item -ItemType Directory -Force docs/historical/superpowers/plans | Out-Null
Move-Item docs/superpowers/plans/2026-06-22-agent-challenge-migrations.md docs/historical/superpowers/plans/2026-06-22-agent-challenge-migrations.md
git add tests/examples docs/add/evidence-index.md docs/add/system-design-implementation.md docs/current_roadmap.md docs/superpowers/plans/2026-06-22-agent-challenge-migrations.md docs/historical/superpowers/plans/2026-06-22-agent-challenge-migrations.md
git commit -m "docs: record data-driven agent challenges"
```
