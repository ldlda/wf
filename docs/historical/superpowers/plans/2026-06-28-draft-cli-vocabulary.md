# Draft CLI Vocabulary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace long draft CLI command names with `wf draft create --capability` and `wf draft add-step --capability`.

**Architecture:** This is a CLI vocabulary cleanup, not a programmatic API rename. Keep the existing Python/RPC/MCP methods and route the new Typer commands to those handlers. Remove the old long CLI commands and update live docs/skills so agents learn one command shape.

**Tech Stack:** Python 3.14, Typer CLI, pytest, ruff, basedpyright.

---

## File Map

- Modify `src/wf_cli/commands/drafts.py`: replace `create-from-capability` with `create`, replace `add-step-from-capability` with `add-step`.
- Modify `tests/wf_cli/test_app.py`: update help tests and assert old long commands are absent.
- Modify `tests/wf_cli/test_remote_target.py` and `tests/wf_cli/test_discovery_lifecycle.py`: update CLI invocations.
- Modify live docs/skills that mention the old CLI commands:
  - `docs/wf_cli.md`
  - `docs/current_roadmap.md`
  - `docs/runbooks/rpc-cli-smoke.md`
  - `docs/runbooks/python-source.md`
  - `skills/wf-cli/SKILL.md`
  - `skills/wf-workflow/SKILL.md`
  - `skills/wf-workflow/references/workflow-lifecycle.md`
  - `skills/wf-workflow/references/draft-workspaces.md`
  - `skills/wf-workflow/references/direct-plan-import.md`
  - `skills/wf-workflow/references/system-model.md`
  - `docs/superpowers/specs/2026-06-27-draft-semantic-authoring-boundary.md`
- Do not edit historical docs except by moving this plan after implementation.

---

### Task 1: Replace Create Command Shape

**Files:**
- Modify: `src/wf_cli/commands/drafts.py`
- Test: `tests/wf_cli/test_app.py`, `tests/wf_cli/test_remote_target.py`, `tests/wf_cli/test_discovery_lifecycle.py`

- [ ] **Step 1: Update failing CLI help tests**

In `tests/wf_cli/test_app.py`, replace:

```python
def test_wf_draft_create_from_capability_help_exists() -> None:
    result = runner.invoke(app, ["draft", "create-from-capability", "--help"])

    assert result.exit_code == 0
    assert "--title" in result.output
```

with:

```python
def test_wf_draft_create_help_accepts_capability_option() -> None:
    result = runner.invoke(app, ["draft", "create", "--help"])

    assert result.exit_code == 0
    output = " ".join(result.output.split())
    assert "--capability" in output
    assert "--title" in output


def test_wf_draft_help_does_not_list_old_create_from_capability() -> None:
    result = runner.invoke(app, ["draft", "--help"])

    assert result.exit_code == 0
    assert "create-from-capability" not in result.output
```

- [ ] **Step 2: Update CLI invocations in tests**

Replace command arrays like:

```python
[
    "draft",
    "create-from-capability",
    "workspace_id",
    "wf.std.constant",
]
```

with:

```python
[
    "draft",
    "create",
    "workspace_id",
    "--capability",
    "wf.std.constant",
]
```

Files to update:

- `tests/wf_cli/test_remote_target.py`
- `tests/wf_cli/test_discovery_lifecycle.py`

Use `rg -n 'create-from-capability' tests/wf_cli` to find every live test hit.

- [ ] **Step 3: Run tests and confirm failure**

Run:

```powershell
uv run pytest tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py tests/wf_cli/test_discovery_lifecycle.py -q -k "draft or create"
```

Expected: failures because `wf draft create` does not exist yet.

- [ ] **Step 4: Implement `wf draft create --capability`**

In `src/wf_cli/commands/drafts.py`, replace:

```python
@app.command("create-from-capability")
def create_from_capability(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    capability_name: Annotated[str, typer.Argument(help="Workflow capability name.")],
    name: Annotated[
        str | None, typer.Option("--name", help="Draft workflow name.")
    ] = None,
    title: Annotated[
        str | None, typer.Option("--title", help="Workspace title.")
    ] = None,
) -> None:
    """Bootstrap a draft workspace from inspect_capability wrapper hints."""
```

with:

```python
@app.command("create")
def create_from_capability(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    capability_name: Annotated[
        str,
        typer.Option(
            "--capability",
            help="Qualified capability name used to bootstrap the draft.",
        ),
    ],
    name: Annotated[
        str | None, typer.Option("--name", help="Draft workflow name.")
    ] = None,
    title: Annotated[
        str | None, typer.Option("--title", help="Workspace title.")
    ] = None,
) -> None:
    """Create a patchable draft workspace from one capability."""
```

Keep the handler call unchanged:

```python
context.handlers.create_draft_workspace_from_capability(...)
```

Do not keep `@app.command("create-from-capability")`.

- [ ] **Step 5: Run create-focused tests**

Run:

```powershell
uv run pytest tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py tests/wf_cli/test_discovery_lifecycle.py -q -k "create"
```

Expected: selected tests pass.

- [ ] **Step 6: Commit**

```powershell
git add src/wf_cli/commands/drafts.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py tests/wf_cli/test_discovery_lifecycle.py
git commit -m "feat: simplify draft create cli"
```

---

### Task 2: Replace Add-Step Command Shape

**Files:**
- Modify: `src/wf_cli/commands/drafts.py`
- Test: `tests/wf_cli/test_app.py`, `tests/wf_cli/test_remote_target.py`

- [ ] **Step 1: Update failing CLI help tests**

In `tests/wf_cli/test_app.py`, replace:

```python
def test_wf_draft_add_step_from_capability_help_explains_explicit_wiring() -> None:
    result = runner.invoke(app, ["draft", "add-step-from-capability", "--help"])
```

with:

```python
def test_wf_draft_add_step_help_explains_explicit_wiring() -> None:
    result = runner.invoke(app, ["draft", "add-step", "--help"])

    assert result.exit_code == 0
    output = " ".join(result.output.split())
    assert "--capability" in output
    assert "--from-step" in output
    assert "--bind-output" in output
    assert "does not guess" in output


def test_wf_draft_help_does_not_list_old_add_step_from_capability() -> None:
    result = runner.invoke(app, ["draft", "--help"])

    assert result.exit_code == 0
    assert "add-step-from-capability" not in result.output
```

- [ ] **Step 2: Update CLI invocations in tests**

Replace:

```python
[
    "draft",
    "add-step-from-capability",
    "workspace_id",
    "--revision",
    "1",
    "--step",
    "render",
    "--capability",
    "local.report.render_markdown_report",
]
```

with:

```python
[
    "draft",
    "add-step",
    "workspace_id",
    "--revision",
    "1",
    "--step",
    "render",
    "--capability",
    "local.report.render_markdown_report",
]
```

Files to update:

- `tests/wf_cli/test_app.py`
- `tests/wf_cli/test_remote_target.py`

Use `rg -n 'add-step-from-capability' tests/wf_cli` to find every live test hit.

- [ ] **Step 3: Run tests and confirm failure**

Run:

```powershell
uv run pytest tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py -q -k "add_step or add-step"
```

Expected: failures because `wf draft add-step` does not exist yet.

- [ ] **Step 4: Implement `wf draft add-step --capability`**

In `src/wf_cli/commands/drafts.py`, replace:

```python
@app.command("add-step-from-capability")
def add_step_from_capability(
```

with:

```python
@app.command("add-step")
def add_step_from_capability(
```

Update the docstring first line to:

```python
"""Add one capability-backed step with explicit route, input, and output wiring.
```

Keep the handler call unchanged:

```python
context.handlers.add_step_from_capability(...)
```

Do not keep `@app.command("add-step-from-capability")`.

- [ ] **Step 5: Run add-step tests**

Run:

```powershell
uv run pytest tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py -q -k "add_step or add-step"
```

Expected: selected tests pass.

- [ ] **Step 6: Commit**

```powershell
git add src/wf_cli/commands/drafts.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py
git commit -m "feat: simplify draft add-step cli"
```

---

### Task 3: Update Live Docs And Skills

**Files:**
- Modify: `docs/wf_cli.md`
- Modify: `docs/current_roadmap.md`
- Modify: `docs/runbooks/rpc-cli-smoke.md`
- Modify: `docs/runbooks/python-source.md`
- Modify: `docs/superpowers/specs/2026-06-27-draft-semantic-authoring-boundary.md`
- Modify: `skills/wf-cli/SKILL.md`
- Modify: `skills/wf-workflow/SKILL.md`
- Modify: `skills/wf-workflow/references/workflow-lifecycle.md`
- Modify: `skills/wf-workflow/references/draft-workspaces.md`
- Modify: `skills/wf-workflow/references/direct-plan-import.md`
- Modify: `skills/wf-workflow/references/system-model.md`
- Move: `docs/superpowers/plans/2026-06-28-draft-cli-vocabulary.md` to `docs/historical/superpowers/plans/2026-06-28-draft-cli-vocabulary.md`

- [ ] **Step 1: Replace old command names in live docs/skills**

Use:

```powershell
rg -n 'create-from-capability|add-step-from-capability|draft create --capability' docs skills -S -g '!docs/historical/**'
```

Update live CLI examples:

```powershell
wf draft create report_ws --capability local.report.extract_report --name report
```

```powershell
wf draft add-step report_ws --revision 3 --step render --capability local.report.render_markdown_report --route ok=__end__
```

Remove text that says:

```text
There is currently no `wf draft create --capability` alias.
```

- [ ] **Step 2: Update semantic authoring spec**

In `docs/superpowers/specs/2026-06-27-draft-semantic-authoring-boundary.md`,
replace public CLI operation names:

```markdown
- `create`
- `add-step`
- `bind`
- `branch`
- `handle`
```

Keep Python method names when the document explicitly discusses internal API
implementation details.

- [ ] **Step 3: Update roadmap**

Add a completed bullet under Priority 1:

```markdown
- Completed: draft CLI vocabulary now uses `wf draft create --capability` and
  `wf draft add-step --capability`, replacing the longer
  `*-from-capability` commands that agents repeatedly guessed around.
```

- [ ] **Step 4: Move plan to historical**

Run:

```powershell
New-Item -ItemType Directory -Force -Path docs/historical/superpowers/plans | Out-Null
Move-Item docs/superpowers/plans/2026-06-28-draft-cli-vocabulary.md docs/historical/superpowers/plans/2026-06-28-draft-cli-vocabulary.md
```

- [ ] **Step 5: Verify no stale live CLI names remain**

Run:

```powershell
rg -n 'create-from-capability|add-step-from-capability' docs skills tests src -S -g '!docs/historical/**'
```

Expected:

- No CLI command docs or tests use the old names.
- Programmatic API/RPC/MCP names may still appear, for example
  `create_draft_workspace_from_capability`, `add_step_from_capability`, and
  `workflow.draft_workspaces.add_step_from_capability`.

- [ ] **Step 6: Commit**

```powershell
git add docs skills tests src docs/historical/superpowers/plans/2026-06-28-draft-cli-vocabulary.md
git commit -m "docs: update draft cli vocabulary"
```

---

### Task 4: Final Verification

**Files:**
- No planned source edits.

- [ ] **Step 1: Run focused CLI tests**

Run:

```powershell
uv run pytest tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py tests/wf_cli/test_discovery_lifecycle.py -q -k "draft or create or add_step or add-step"
```

Expected: all selected tests pass.

- [ ] **Step 2: Run broader affected suites**

Run:

```powershell
uv run pytest tests/wf_cli tests/docs -q
```

Expected: all tests pass. If docs tests are not present in the current checkout,
record that and continue with the CLI tests.

- [ ] **Step 3: Run lint, format, and type checks**

Run:

```powershell
uv run ruff check
uv run ruff format --check
uv run basedpyright --level error
git diff --check
```

Expected:

- Ruff clean.
- Format clean.
- Basedpyright reports `0 errors`.
- `git diff --check` has no whitespace errors. CRLF warnings are acceptable on
  Windows.

- [ ] **Step 4: Optional smoke command**

Run:

```powershell
uv run wf --config wf.config.json draft create --help
uv run wf --config wf.config.json draft add-step --help
```

Expected:

- `create` help shows `--capability`.
- `add-step` help shows `--capability`, `--route`, `--input`, and
  `--bind-output`.

- [ ] **Step 5: Commit final cleanup if needed**

```powershell
git status --short
git add <only files changed by cleanup>
git commit -m "fix: polish draft cli vocabulary"
```

Skip this commit if the tree is already clean after Task 3.

---

## Self-Review Notes

- This plan intentionally changes only CLI command names and live docs/skills.
- It does not rename Python/RPC/MCP programmatic method names.
- It removes the old long CLI names rather than keeping aliases.
- Future work can rename RPC/MCP tools if evidence shows model confusion there too.
