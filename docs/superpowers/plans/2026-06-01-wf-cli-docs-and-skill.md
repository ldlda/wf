# wf CLI Docs And Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create real user-facing `wf` CLI documentation and a small agent skill, then update `wf explain` cards to reference those docs instead of planning specs.

**Architecture:** Treat `docs/superpowers/*` as planning history only, not runtime/user guidance. The canonical CLI reference should live at `docs/wf_cli.md`; the optional repo-local skill should live at `skills/wf-cli/SKILL.md` and point agents to the real doc plus the safest command flow.

**Tech Stack:** Markdown docs, existing `wf_cli.explain` registry, pytest, ruff.

---

## Scope

Create:

```text
docs/wf_cli.md
skills/wf-cli/SKILL.md
```

Modify:

```text
docs/README.md
src/wf_cli/explain/entries.py
tests/wf_cli/test_explain.py
```

Do not add command aliases in this slice. `wf cap` and `wf deploy` are the real registered command names.

Do not link `wf explain` runtime guidance to:

```text
docs/superpowers/specs/*
docs/superpowers/plans/*
```

Those are planning artifacts, not user/operator docs.

## Task 1: Add Real CLI User Documentation

**Files:**

- Create: `docs/wf_cli.md`
- Modify: `docs/README.md`

- [ ] **Step 1: Create `docs/wf_cli.md`**

Create `docs/wf_cli.md`:

```markdown
# wf CLI

`wf` is the workflow platform command-line interface. It is a second front door
beside MCP: useful for shell-driven authoring, local validation, file-based
patches, and agent workflows that do better with commands than giant MCP
schemas.

`wf` uses the same config/store stack as the MCP server in v1:

```bash
wf --config wf_mcp.config.json <command>
```

If `--config` is omitted, `wf_mcp.config.json` is used.

## Output Policy

JSON is the default output format for every command.

List/discovery commands may support:

```text
--format json      # complete machine-readable payload
--format ids       # one identifier per line
--format compact   # one concise line per item
```

Detail and mutation commands are JSON-only unless documented otherwise.

There is no `table` format in v1.

## Lifecycle

The normal CLI workflow is:

1. Inspect capabilities.
2. Create a draft workspace from a capability.
3. Inspect or patch the draft.
4. Validate the draft.
5. Save an artifact.
6. Save a deployment with source bindings.
7. Validate the deployment.
8. Run the deployment.
9. Read bounded trace detail only when debugging.

## Capability Discovery

List capabilities:

```bash
wf cap list
wf cap list --source wf.std --format ids
wf cap list --query echo --format compact
```

Inspect one capability:

```bash
wf cap inspect wf.std.concat
```

`inspect` returns the full contract, including `wrapper_hints` when available.
Hints are scaffolding, not semantic guarantees.

## Draft Workspaces

Create a draft from a capability:

```bash
wf draft create-from-capability concat_ws wf.std.concat --name concat_ws
```

List and inspect drafts:

```bash
wf draft list --format compact
wf draft inspect concat_ws
wf draft inspect concat_ws --include-draft
```

Patch a draft with RFC 6902 JSON Patch:

```bash
wf draft patch concat_ws \
  --revision 1 \
  --input '[{"op":"replace","path":"/name","value":"concat_ws_v2"}]'
```

Validate:

```bash
wf draft validate concat_ws
```

Save as an artifact:

```bash
wf draft save concat_ws \
  --artifact concat_ws \
  --version 1 \
  --title "Concat Workflow" \
  --outcome ok \
  --binding wf.std=wf.std
```

Use `--kind wrapper` when saving a callable wrapper artifact:

```bash
wf draft save concat_ws \
  --artifact concat_wrapper \
  --version 1 \
  --title "Concat Wrapper" \
  --kind wrapper \
  --outcome ok \
  --binding wf.std=wf.std
```

## Artifacts

List and inspect artifacts:

```bash
wf artifact list --format ids
wf artifact list --kind wrapper --format compact
wf artifact inspect concat_ws 1
```

Artifacts are immutable saved workflow definitions. List output is compact by
design; use `inspect` for full details.

## Deployments

Save a deployment from flags:

```bash
wf deploy save concat_ws.default \
  --artifact concat_ws \
  --version 1 \
  --binding wf.std=wf.std
```

Save a deployment from JSON:

```bash
wf deploy save --input-file deployment.json
```

List, inspect, validate, and delete:

```bash
wf deploy list --format compact
wf deploy inspect concat_ws.default
wf deploy validate concat_ws.default
wf deploy validate concat_ws.default --live
wf deploy delete concat_ws.default
```

`--live` performs opt-in upstream liveness checks. Static validation can pass
even when a live external source is temporarily unreachable.

## Runs And Traces

Start a deployment:

```bash
wf run start concat_ws.default \
  --input '{"items":["red","blue"],"separator":" + "}'
```

Inspect a run without trace detail:

```bash
wf run inspect run_123
```

Read a bounded trace slice:

```bash
wf run trace run_123 --from 0 --limit 25
```

Trace output can be large. Always request a bounded range.

## Explain

Explain stable diagnostic/error codes:

```bash
wf explain source_missing
wf explain deployment_unrunnable --format markdown
wf explain --input-file validation-output.json
wf explain --list --format compact
```

`wf explain` is exact-match and docs-backed. It is not fuzzy search and does not
generate prose.

## Common Diagnostics

### `source_missing`

A required logical source is not available or not bound.

Check:

```bash
wf deploy inspect <deployment_id>
wf cap list
wf deploy validate <deployment_id> --live
```

### `binding_missing`

A deployment is missing a required logical-to-concrete source binding.

Check artifact requirements, then save the deployment with all required
bindings:

```bash
wf deploy save <deployment_id> \
  --artifact <artifact_id> \
  --version <version> \
  --binding <logical>=<concrete>
```

### `capability_missing`

The bound source does not expose a required capability.

Check:

```bash
wf cap list --source <source_id>
wf deploy inspect <deployment_id>
```

### `schema_changed`

A saved dependency schema no longer matches the live capability. Inspect the
live capability, patch the draft or wrapper, and save a new artifact version.

### `deployment_unrunnable`

The deployment failed validation and should not be run yet.

Check:

```bash
wf deploy validate <deployment_id>
wf explain --input-file validation-output.json
```

## Known Limits

- The CLI reuses `wf_mcp` service/config/store wiring in v1.
- Config loading registers stores and connections, but not arbitrary in-memory
  test `NodeSpec` functions.
- Targeted draft editing helpers such as `wf draft step add` are not in v1.
- `wf` does not replace MCP resources/prompts or interactive MCP clients.
```

- [ ] **Step 2: Add CLI doc to docs index**

Modify `docs/README.md` under `## Current Overview` or a new `## CLI` section:

```markdown
- [`wf_cli.md`](wf_cli.md): workflow platform CLI commands, output formats,
  lifecycle flow, and common diagnostics.
```

- [ ] **Step 3: Verify doc links manually**

Run:

```bash
Test-Path docs/wf_cli.md
Select-String -Path docs/README.md -Pattern 'wf_cli.md'
```

Expected: both show the new doc exists and is indexed.

## Task 2: Add Repo-Local Agent Skill

**Files:**

- Create: `skills/wf-cli/SKILL.md`

- [ ] **Step 1: Create `skills/wf-cli/SKILL.md`**

Create `skills/wf-cli/SKILL.md`:

```markdown
---
name: wf-cli
description: Use when authoring, validating, deploying, running, or debugging workflows through the repo-local `wf` CLI.
---

# wf CLI

Use the `wf` CLI when an agent needs a shell-friendly workflow lifecycle:

1. Discover capabilities.
2. Create or patch a draft workspace.
3. Validate the draft.
4. Save an artifact.
5. Save and validate a deployment.
6. Run the deployment.
7. Read bounded trace slices only when debugging.

Canonical docs:

- `docs/wf_cli.md`
- `docs/workflow_capabilities.md`
- `docs/workflow_drafts.md`
- `docs/workflow_artifacts.md`
- `docs/durable_run_operations.md`

## Core Commands

```bash
wf cap list --format ids
wf cap inspect <capability>

wf draft create-from-capability <workspace_id> <capability>
wf draft inspect <workspace_id> --include-draft
wf draft patch <workspace_id> --revision <n> --input-file patch.json
wf draft validate <workspace_id>
wf draft save <workspace_id> --artifact <artifact_id> --version <n> --title <title>

wf deploy save <deployment_id> --artifact <artifact_id> --version <n> --binding <logical>=<concrete>
wf deploy validate <deployment_id>
wf run start <deployment_id> --input-file input.json
wf run trace <run_id> --from 0 --limit 25
```

## Rules

- Prefer `--input-file` for large JSON.
- Prefer `--format ids` or `--format compact` for discovery.
- Do not request unbounded traces.
- Do not treat wrapper hints as semantic guarantees.
- If validation fails, run `wf explain <code>` or `wf explain --input-file <validation-output.json>`.
- Do not use docs under `docs/superpowers/` as user-facing runtime guidance.
```

- [ ] **Step 2: Do not wire skill installation**

Do not add marketplace/plugin installation logic in this slice. This repo-local
skill is a source document for future packaging; it is not automatically active
until a user installs or copies it into their agent environment.

## Task 3: Update `wf explain` Doc References

**Files:**

- Modify: `src/wf_cli/explain/entries.py`
- Test: `tests/wf_cli/test_explain.py`

- [ ] **Step 1: Add tests that all explain doc refs are user-facing and existing**

Append to `tests/wf_cli/test_explain.py`:

```python
from pathlib import Path


def test_explain_related_docs_do_not_point_to_planning_artifacts() -> None:
    for entry in DEFAULT_EXPLAIN_REGISTRY.list_full_entries():
        for related_doc in entry.related_docs:
            assert "docs/superpowers/" not in related_doc


def test_explain_related_doc_files_exist() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    for entry in DEFAULT_EXPLAIN_REGISTRY.list_full_entries():
        for related_doc in entry.related_docs:
            path_text = related_doc.split("#", 1)[0]
            if path_text.startswith("docs/"):
                assert (repo_root / path_text).exists(), path_text
```

- [ ] **Step 2: Add registry full-entry accessor**

Modify `src/wf_cli/explain/registry.py`:

```python
    def list_full_entries(self) -> list[ExplainCard]:
        """Return full cards for internal validation/tests."""
        return list(self._entries.values())
```

- [ ] **Step 3: Update explain cards to use `docs/wf_cli.md`**

Modify `src/wf_cli/explain/entries.py`:

```python
related_docs=[
    "docs/wf_cli.md#deployments",
    "docs/workflow_capabilities.md",
],
```

Use these mappings:

```text
source_missing          -> docs/wf_cli.md#common-diagnostics, docs/workflow_capabilities.md
source_unreachable      -> docs/wf_cli.md#deployments, docs/wf_mcp_troubleshooting.md
binding_missing         -> docs/wf_cli.md#deployments, docs/workflow_artifacts.md
capability_missing      -> docs/wf_cli.md#capability-discovery, docs/workflow_capabilities.md
schema_changed          -> docs/wf_cli.md#common-diagnostics, docs/schema_validation.md
deployment_unrunnable   -> docs/wf_cli.md#common-diagnostics, docs/current_roadmap.md
```

- [ ] **Step 4: Run explain tests**

Run:

```bash
uv run pytest tests/wf_cli/test_explain.py -q
```

Expected: pass.

## Task 4: Verification

**Files:**

- No new files unless lint/format requires cleanup.

- [ ] **Step 1: Run focused CLI tests**

Run:

```bash
uv run pytest tests/wf_cli -q
```

Expected: all CLI tests pass.

- [ ] **Step 2: Run focused lint**

Run:

```bash
uv run ruff check src/wf_cli tests/wf_cli
```

Expected: no lint errors.

- [ ] **Step 3: Run focused format check**

Run:

```bash
uv run ruff format --check src/wf_cli tests/wf_cli
```

Expected: no formatting changes required. If this fails, run:

```bash
uv run ruff format src/wf_cli tests/wf_cli
```

Then rerun the format check.

- [ ] **Step 4: Run docs path check**

Run:

```bash
Test-Path docs/wf_cli.md
Test-Path skills/wf-cli/SKILL.md
rg -n "docs/superpowers/" src/wf_cli/explain docs/wf_cli.md skills/wf-cli/SKILL.md
```

Expected:

- `docs/wf_cli.md` exists.
- `skills/wf-cli/SKILL.md` exists.
- `rg` finds no `docs/superpowers/` runtime guidance references in those paths.

## Self-Review Checklist

- [ ] `wf explain` cards no longer link to `docs/superpowers/specs` or `docs/superpowers/plans`.
- [ ] `docs/wf_cli.md` contains the lifecycle that the CLI actually supports today.
- [ ] `docs/README.md` points to the new CLI doc.
- [ ] The skill is repo-local documentation only; no install/packaging behavior was added.
- [ ] Tests verify explain-card doc refs are not stale.
