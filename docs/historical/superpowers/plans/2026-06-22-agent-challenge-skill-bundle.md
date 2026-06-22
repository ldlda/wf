# Agent Challenge Skill Bundle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the workflow/CLI skills into a coherent, implementation-free instruction bundle that the challenge harness can copy reproducibly into trial workspaces.

**Architecture:** Keep `skills/wf-cli` focused on shell operation and `skills/wf-workflow` focused on domain lifecycle/authoring. An explicit YAML bundle manifest lists every copied file and destination; tests enforce existence, uniqueness, absence of implementation/test pointers, and current `wf schema` guidance.

**Tech Stack:** Markdown skills, YAML, Python 3.14, PyYAML, pytest.

---

## File Structure

- Modify `skills/wf-cli/SKILL.md`: shell-first discovery and lifecycle commands.
- Modify `skills/wf-workflow/SKILL.md`: domain routing and progressive references.
- Modify `skills/wf-workflow/references/system-model.md`: concise object model.
- Modify `skills/wf-workflow/references/workflow-lifecycle.md`: end-to-end order.
- Modify `skills/wf-workflow/references/capabilities-and-wrappers.md`: capability contracts.
- Modify `skills/wf-workflow/references/draft-workspaces.md`: draft shape/edit path.
- Modify `skills/wf-workflow/references/direct-plan-import.md`: raw-plan shape.
- Modify `skills/wf-workflow/references/troubleshooting.md`: public-surface recovery.
- Create `examples/agent_challenges/instruction_bundles/workflow_cli.yaml`: explicit copy manifest.
- Create `tests/examples/test_agent_challenge_skill_bundle.py`: bundle and content contract.

### Task 1: Define The Bundle Contract With Tests

**Files:**
- Create: `tests/examples/test_agent_challenge_skill_bundle.py`
- Create: `examples/agent_challenges/instruction_bundles/workflow_cli.yaml`

- [ ] **Step 1: Write failing manifest tests**

Create `tests/examples/test_agent_challenge_skill_bundle.py`:

```python
from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = (
    ROOT
    / "examples"
    / "agent_challenges"
    / "instruction_bundles"
    / "workflow_cli.yaml"
)


def _bundle() -> dict[str, object]:
    loaded = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _entries() -> list[dict[str, str]]:
    raw = _bundle()["files"]
    assert isinstance(raw, list)
    entries: list[dict[str, str]] = []
    for value in raw:
        assert isinstance(value, dict)
        assert isinstance(value.get("source"), str)
        assert isinstance(value.get("destination"), str)
        entries.append(value)
    return entries


def test_workflow_cli_bundle_has_unique_existing_files() -> None:
    bundle = _bundle()
    entries = _entries()

    assert bundle["version"] == 1
    assert bundle["id"] == "workflow-cli"
    assert len(entries) >= 8
    sources = [entry["source"] for entry in entries]
    destinations = [entry["destination"] for entry in entries]
    assert len(sources) == len(set(sources))
    assert len(destinations) == len(set(destinations))
    assert all((ROOT / source).is_file() for source in sources)
    assert all(not Path(destination).is_absolute() for destination in destinations)
    assert all(".." not in Path(destination).parts for destination in destinations)


def test_workflow_cli_bundle_uses_public_surfaces_not_implementation_files() -> None:
    contents = "\n".join(
        (ROOT / entry["source"]).read_text(encoding="utf-8")
        for entry in _entries()
    )

    assert "tests/" not in contents
    assert "src/" not in contents
    assert "test_" not in contents
    assert "wf schema" in contents
    assert "wf draft validate" in contents
    assert "wf deploy validate" in contents
    assert "wf run trace" in contents
    assert "empty command group" not in contents
    assert "no schema subcommands" not in contents


def test_bundle_destinations_form_two_skills() -> None:
    destinations = {entry["destination"] for entry in _entries()}

    assert "wf-cli/SKILL.md" in destinations
    assert "wf-workflow/SKILL.md" in destinations
    assert any(path.startswith("wf-workflow/references/") for path in destinations)
```

- [ ] **Step 2: Run tests and verify the manifest is missing**

```powershell
uv run pytest tests/examples/test_agent_challenge_skill_bundle.py -q
```

Expected: fail because `workflow_cli.yaml` does not exist.

- [ ] **Step 3: Add the explicit bundle manifest**

Create `examples/agent_challenges/instruction_bundles/workflow_cli.yaml`:

```yaml
version: 1
id: workflow-cli
description: Public workflow lifecycle and CLI instructions for agent trials.
files:
  - source: skills/wf-cli/SKILL.md
    destination: wf-cli/SKILL.md
  - source: skills/wf-workflow/SKILL.md
    destination: wf-workflow/SKILL.md
  - source: skills/wf-workflow/references/system-model.md
    destination: wf-workflow/references/system-model.md
  - source: skills/wf-workflow/references/workflow-lifecycle.md
    destination: wf-workflow/references/workflow-lifecycle.md
  - source: skills/wf-workflow/references/capabilities-and-wrappers.md
    destination: wf-workflow/references/capabilities-and-wrappers.md
  - source: skills/wf-workflow/references/draft-workspaces.md
    destination: wf-workflow/references/draft-workspaces.md
  - source: skills/wf-workflow/references/direct-plan-import.md
    destination: wf-workflow/references/direct-plan-import.md
  - source: skills/wf-workflow/references/troubleshooting.md
    destination: wf-workflow/references/troubleshooting.md
```

- [ ] **Step 4: Run the existence/shape tests**

```powershell
uv run pytest tests/examples/test_agent_challenge_skill_bundle.py::test_workflow_cli_bundle_has_unique_existing_files tests/examples/test_agent_challenge_skill_bundle.py::test_bundle_destinations_form_two_skills -q
```

Expected: pass; public-surface content test may still fail until Tasks 2-3.

- [ ] **Step 5: Commit the bundle contract**

```powershell
git add examples/agent_challenges/instruction_bundles/workflow_cli.yaml tests/examples/test_agent_challenge_skill_bundle.py
git commit -m "test: define agent challenge skill bundle"
```

### Task 2: Make `wf-cli` A Public-Surface Skill

**Files:**
- Modify: `skills/wf-cli/SKILL.md`
- Test: `tests/examples/test_agent_challenge_skill_bundle.py`

- [ ] **Step 1: Replace stale schema and discovery guidance**

Keep the existing frontmatter and lifecycle command inventory. Replace the
schema WIP rule with:

```markdown
## Public Discovery Order

Use public CLI surfaces before broader documentation or implementation search:

1. `wf status`
2. `wf cap list --format ids`
3. `wf cap inspect <capability>`
4. `wf schema` to list workflow document/component shapes
5. `wf schema draft`, `wf schema raw`, or `wf schema <Component>`
6. `wf explain <diagnostic-code>` after validation failures

Use `wf schema <name> --verbose` only when the complete JSON Schema is required;
the default compact outline is preferred for agent context.
```

Add these rules under `## Rules`:

```markdown
- Prefer `wf schema` over searching tests or implementation code for draft/raw
  plan shape.
- Treat compact schema output as authoring guidance; use validation commands as
  the source of truth for a concrete document.
- If public commands and supplied skills are insufficient, report the exact
  blocker instead of guessing undocumented fields.
```

- [ ] **Step 2: Remove challenge/evaluator-only policy from the product skill**

Ensure `skills/wf-cli/SKILL.md` contains no instructions about challenge
self-reports, contamination flags, model grading, prior trials, or test-file
inspection. Those belong in the harness base/profile prompt.

- [ ] **Step 3: Run the public-surface content test**

```powershell
uv run pytest tests/examples/test_agent_challenge_skill_bundle.py::test_workflow_cli_bundle_uses_public_surfaces_not_implementation_files -q
```

Expected: may still fail on workflow references; the `wf-cli` file itself no
longer contains stale or implementation-oriented guidance.

- [ ] **Step 4: Commit the CLI skill**

```powershell
git add skills/wf-cli/SKILL.md
git commit -m "docs: make wf cli skill schema-first"
```

### Task 3: Reorganize Workflow References Around Public Models

**Files:**
- Modify: `skills/wf-workflow/SKILL.md`
- Modify: `skills/wf-workflow/references/system-model.md`
- Modify: `skills/wf-workflow/references/workflow-lifecycle.md`
- Modify: `skills/wf-workflow/references/capabilities-and-wrappers.md`
- Modify: `skills/wf-workflow/references/draft-workspaces.md`
- Modify: `skills/wf-workflow/references/direct-plan-import.md`
- Modify: `skills/wf-workflow/references/troubleshooting.md`
- Test: `tests/examples/test_agent_challenge_skill_bundle.py`

- [ ] **Step 1: Add reference routing to the main workflow skill**

Under `## References`, make the routing explicit:

```markdown
Read only the reference needed for the current task:

- Start with `system-model.md` when lifecycle vocabulary is unclear.
- Use `workflow-lifecycle.md` for operation order.
- Use `capabilities-and-wrappers.md` before selecting a source capability.
- Use `draft-workspaces.md` for iterative editing.
- Use `direct-plan-import.md` only when a complete raw plan is required.
- Use `troubleshooting.md` after a public validation/run failure.

Before authoring JSON, query the live public model with `wf schema`; the
references explain semantics while the command reflects the current shape.
```

- [ ] **Step 2: Remove duplicate command inventories from the domain skill**

Keep lifecycle semantics in `wf-workflow/SKILL.md`, but leave full shell syntax
to `wf-cli/SKILL.md` and the focused references. Keep only one representative
command per branch (`draft` versus `raw`) in the domain skill.

- [ ] **Step 3: Add schema commands to draft and raw references**

At the start of `draft-workspaces.md`, add:

```markdown
Inspect the current draft model before writing or patching JSON:

    wf schema draft
    wf schema DraftUseStep

Use `--verbose` only when a complete JSON Schema is required.
```

At the start of `direct-plan-import.md`, add:

```markdown
Inspect the current raw-plan and component models before writing JSON:

    wf schema raw
    wf schema NodeUse
    wf schema InputPathBinding
    wf schema OutputBinding

Use `--verbose` only when a complete JSON Schema is required.
```

- [ ] **Step 4: Keep troubleshooting on public evidence**

Ensure `troubleshooting.md` directs agents to:

```text
wf status
wf cap inspect
wf draft validate
wf deploy validate
wf run inspect
wf run trace --from <n> --limit <n>
wf explain <code>
```

Remove directions to inspect `tests/`, `src/`, implementation examples, or
historical plans.

- [ ] **Step 5: Keep reference responsibilities distinct**

Verify:

- `system-model.md` defines objects and boundaries, not command transcripts;
- `workflow-lifecycle.md` defines order and branch points;
- `draft-workspaces.md` owns draft shape/mapping semantics;
- `direct-plan-import.md` owns raw-plan shape/mapping semantics;
- `capabilities-and-wrappers.md` owns source/capability distinctions;
- `troubleshooting.md` owns recovery commands.

- [ ] **Step 6: Run all bundle tests**

```powershell
uv run pytest tests/examples/test_agent_challenge_skill_bundle.py -q
```

Expected: all pass.

- [ ] **Step 7: Commit workflow skill reorganization**

```powershell
git add skills/wf-workflow tests/examples/test_agent_challenge_skill_bundle.py
git commit -m "docs: reorganize workflow agent instructions"
```

### Task 4: Verify Copyability And Record Completion

**Files:**
- Modify: `tests/examples/test_agent_challenge_skill_bundle.py`
- Modify: `docs/current_roadmap.md`
- Move after completion: `docs/superpowers/plans/2026-06-22-agent-challenge-skill-bundle.md` to `docs/historical/superpowers/plans/2026-06-22-agent-challenge-skill-bundle.md`

- [ ] **Step 1: Add a copy smoke test**

Append:

```python
import shutil


def test_workflow_cli_bundle_copies_to_agent_skill_root(tmp_path: Path) -> None:
    destination_root = tmp_path / ".agent" / "skills"
    for entry in _entries():
        source = ROOT / entry["source"]
        destination = destination_root / entry["destination"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    assert (destination_root / "wf-cli" / "SKILL.md").is_file()
    assert (destination_root / "wf-workflow" / "SKILL.md").is_file()
    assert (
        destination_root
        / "wf-workflow"
        / "references"
        / "direct-plan-import.md"
    ).is_file()
```

- [ ] **Step 2: Run focused verification**

```powershell
uv run pytest tests/examples/test_agent_challenge_skill_bundle.py -q
uv run ruff check tests/examples/test_agent_challenge_skill_bundle.py
uv run ruff format --check tests/examples/test_agent_challenge_skill_bundle.py
uv run basedpyright --level error tests/examples/test_agent_challenge_skill_bundle.py
git diff --check
```

Expected: all tests/checks pass; only accepted Windows CRLF warnings may appear.

- [ ] **Step 3: Update the roadmap**

Add:

```markdown
- Completed: workflow/CLI agent instructions now form an explicit copyable
  bundle for controlled challenge profiles, use `wf schema` for public shape
  discovery, and avoid implementation/test-file guidance.
```

- [ ] **Step 4: Archive and commit the plan**

```powershell
New-Item -ItemType Directory -Force docs/historical/superpowers/plans | Out-Null
Move-Item docs/superpowers/plans/2026-06-22-agent-challenge-skill-bundle.md docs/historical/superpowers/plans/2026-06-22-agent-challenge-skill-bundle.md
git add docs/current_roadmap.md docs/superpowers/plans/2026-06-22-agent-challenge-skill-bundle.md docs/historical/superpowers/plans/2026-06-22-agent-challenge-skill-bundle.md tests/examples/test_agent_challenge_skill_bundle.py
git commit -m "docs: record agent challenge skill bundle"
```
