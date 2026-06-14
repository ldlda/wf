# Local CLI Config Composition Implementation Plan

Status: implemented and archived.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `wf --config <neutral-config> --local ...` build the same configured local server sources that `wf-rpc-server --config <neutral-config>` builds, including Python sources.

**Architecture:** `wf_cli.context.load_cli_context()` already parses neutral workflow configs, but its local branch calls `build_local_static_workflow_server(store.root)`, which ignores `server.sources`. Replace that branch with the existing composition boundary `wf_server.config.build_workflow_server_from_workflow_config(config)` so local CLI mode means "same-process server from this config" instead of "static built-ins only." Keep `--url` remote override and legacy `wf_mcp.config.json` behavior unchanged.

**Tech Stack:** Python 3.14, Typer CLI, pytest, `wf_config`, `wf_server.config`, `wf_sources_python`.

---

## File Structure

- Modify `src/wf_cli/context.py`: import and use the config-aware server builder in the local neutral-config branch.
- Modify `tests/wf_cli/test_context.py`: update the existing store override test and add a Python-source regression test for `load_cli_context(..., force_local=True)`.
- Modify `tests/wf_cli/test_remote_target.py`: add a CLI-level `--local --config` regression test that lists a configured Python source.
- Modify `docs/wf_cli.md`: clarify that `--local` still uses the selected `--config` and composes configured server sources.
- Modify `docs/current_roadmap.md`: mark the local-config CLI composition gap completed.

Do not touch the already-completed RPC create-from-plan or opencode harness work.

---

### Task 1: Prove Local CLI Context Composes Python Sources

**Files:**
- Modify: `tests/wf_cli/test_context.py`

- [ ] **Step 1: Add imports needed by async capability assertions**

At the top of `tests/wf_cli/test_context.py`, add `pytest`:

```python
import pytest
```

Keep the existing imports. If `build_local_static_workflow_server` becomes unused after later steps, remove that import in Task 2.

- [ ] **Step 2: Add a helper that writes a temporary Python source config**

Add this helper near the existing tests in `tests/wf_cli/test_context.py`:

```python
def _write_python_source_config(root: Path, *, target: dict[str, object]) -> Path:
    source_root = root / "source"
    source_root.mkdir()
    (source_root / "ops.py").write_text(
        """
from pydantic import BaseModel

from wf_authoring import node


class EchoInput(BaseModel):
    text: str


class EchoOutput(BaseModel):
    text: str


@node(name="echo")
def echo(payload: EchoInput) -> EchoOutput:
    return EchoOutput(text=payload.text)


registry = [echo]
""".lstrip(),
        encoding="utf-8",
    )
    config_path = root / "wf.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "client": {"target": target},
                "server": {
                    "store": {"kind": "filesystem", "root": ".wf_store"},
                    "sources": [
                        {
                            "kind": "python",
                            "id": "local.ops",
                            "path": "source",
                            "module": "ops",
                            "registry": "registry",
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    return config_path
```

- [ ] **Step 3: Add the failing context-level regression test**

Add this test to `tests/wf_cli/test_context.py`:

```python
@pytest.mark.asyncio
async def test_load_cli_context_local_composes_configured_python_sources(
    tmp_path: Path,
) -> None:
    config_path = _write_python_source_config(
        tmp_path,
        target={
            "kind": "rpc_http",
            "url": "http://127.0.0.1:8765/rpc",
        },
    )

    context = load_cli_context(config_path, force_local=True)

    listed = await context.handlers.list_capabilities(
        source_id="local.ops",
        limit=100,
    )
    assert {
        capability["name"] for capability in listed["capabilities"]
    } == {"local.ops.echo"}
```

- [ ] **Step 4: Run the failing test**

Run:

```bash
uv run pytest tests/wf_cli/test_context.py::test_load_cli_context_local_composes_configured_python_sources -q
```

Expected before implementation: FAIL because `local.ops.echo` is missing; the local branch only loads built-in static sources.

- [ ] **Step 5: Commit the red test**

```bash
git add tests/wf_cli/test_context.py
git commit -m "test: expose local cli config source composition gap"
```

---

### Task 2: Use Config-Aware Server Builder In Local CLI Mode

**Files:**
- Modify: `src/wf_cli/context.py`
- Modify: `tests/wf_cli/test_context.py`

- [ ] **Step 1: Update imports in `src/wf_cli/context.py`**

Replace:

```python
from wf_server import build_local_static_workflow_server
```

with:

```python
from wf_server.config import build_workflow_server_from_workflow_config
```

- [ ] **Step 2: Replace the local neutral-config builder call**

In `load_cli_context()`, replace the local branch body:

```python
    if force_local or isinstance(target, LocalTargetConfig):
        store = config.server.workflow_store
        if not isinstance(store, FilesystemStoreConfig):
            raise ValueError("local CLI target currently requires filesystem store")
        server = build_local_static_workflow_server(store.root)
        return CliContext(
            config_path=resolved_config_path,
            service=None,
            handlers=server.api,
            source_admin=server.source_admin,
            admin=server.admin,
            verbose=verbose,
        )
```

with:

```python
    if force_local or isinstance(target, LocalTargetConfig):
        store = config.server.workflow_store
        if not isinstance(store, FilesystemStoreConfig):
            raise ValueError("local CLI target currently requires filesystem store")
        server = build_workflow_server_from_workflow_config(config)
        return CliContext(
            config_path=resolved_config_path,
            service=None,
            handlers=server.api,
            source_admin=server.source_admin,
            admin=server.admin,
            verbose=verbose,
        )
```

Keep the filesystem-store guard. It preserves the current local CLI error contract and gives a clearer CLI-facing message before the server builder raises.

- [ ] **Step 3: Update the existing store override test monkeypatch**

In `tests/wf_cli/test_context.py`, replace the import:

```python
from wf_server import build_local_static_workflow_server
```

with:

```python
from wf_server.config import build_workflow_server_from_workflow_config
```

Then update `test_load_cli_context_local_uses_workflow_store_override()` so it patches the new builder:

```python
def test_load_cli_context_local_uses_workflow_store_override(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path = tmp_path / "wf.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "client": {"target": {"kind": "local"}},
                "server": {
                    "store": {"kind": "filesystem", "root": ".default"},
                    "stores": {
                        "workflow": {
                            "kind": "filesystem",
                            "root": ".workflow",
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def fake_build_workflow_server_from_workflow_config(config):
        captured["store_root"] = config.server.workflow_store.root
        return build_workflow_server_from_workflow_config(config)

    monkeypatch.setattr(
        "wf_cli.context.build_workflow_server_from_workflow_config",
        fake_build_workflow_server_from_workflow_config,
    )

    context = load_cli_context(config_path)

    assert context.service is None
    assert captured["store_root"] == (tmp_path / ".workflow").resolve()
```

This keeps the old assertion, but verifies the full config reaches the composition boundary.

- [ ] **Step 4: Run context tests**

Run:

```bash
uv run pytest tests/wf_cli/test_context.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit the implementation**

```bash
git add src/wf_cli/context.py tests/wf_cli/test_context.py
git commit -m "fix: compose configured sources for local cli target"
```

---

### Task 3: Prove CLI `--local --config` Lists Configured Sources

**Files:**
- Modify: `tests/wf_cli/test_remote_target.py`

- [ ] **Step 1: Add a CLI-level regression helper if needed**

If `tests/wf_cli/test_remote_target.py` does not already have a Python-source config helper, add this helper near the top-level test helpers:

```python
def _write_python_source_cli_config(root: Path) -> Path:
    source_root = root / "source"
    source_root.mkdir()
    (source_root / "ops.py").write_text(
        """
from pydantic import BaseModel

from wf_authoring import node


class EchoInput(BaseModel):
    text: str


class EchoOutput(BaseModel):
    text: str


@node(name="echo")
def echo(payload: EchoInput) -> EchoOutput:
    return EchoOutput(text=payload.text)


registry = [echo]
""".lstrip(),
        encoding="utf-8",
    )
    config_path = root / "wf.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "client": {
                    "target": {
                        "kind": "rpc_http",
                        "url": "http://127.0.0.1:8765/rpc",
                    }
                },
                "server": {
                    "store": {"kind": "filesystem", "root": ".wf_store"},
                    "sources": [
                        {
                            "kind": "python",
                            "id": "local.ops",
                            "path": "source",
                            "module": "ops",
                            "registry": "registry",
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    return config_path
```

- [ ] **Step 2: Add the CLI invocation test**

Add this test to `tests/wf_cli/test_remote_target.py`:

```python
def test_wf_local_uses_selected_config_sources(tmp_path: Path) -> None:
    config_path = _write_python_source_cli_config(tmp_path)

    result = CliRunner().invoke(
        app,
        [
            "--config",
            str(config_path),
            "--local",
            "cap",
            "list",
            "--source",
            "local.ops",
            "--limit",
            "100",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert {
        capability["name"] for capability in payload["capabilities"]
    } == {"local.ops.echo"}
```

- [ ] **Step 3: Run the focused CLI test**

Run:

```bash
uv run pytest tests/wf_cli/test_remote_target.py::test_wf_local_uses_selected_config_sources -q
```

Expected: PASS.

- [ ] **Step 4: Run nearby CLI target tests**

Run:

```bash
uv run pytest tests/wf_cli/test_context.py tests/wf_cli/test_remote_target.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit the CLI regression test**

```bash
git add tests/wf_cli/test_remote_target.py
git commit -m "test: cover local cli configured sources"
```

---

### Task 4: Document Local Target Semantics

**Files:**
- Modify: `docs/wf_cli.md`
- Modify: `docs/current_roadmap.md`

- [ ] **Step 1: Update `docs/wf_cli.md` target selection text**

Find the target-selection or root-options section in `docs/wf_cli.md`. Add this paragraph near the `--local`, `--url`, and `--config` explanation:

```markdown
`--local` still uses the selected `--config` file. For neutral workflow configs,
it builds the configured server in the CLI process, including configured Python
sources and other local source providers. Use `--url` when you want to force the
CLI to talk to an already-running `wf-rpc-server`; `--local` and `--url` are
mutually exclusive.
```

If an older paragraph says `--local` only builds a static filesystem server, replace it with the paragraph above.

- [ ] **Step 2: Update roadmap**

In `docs/current_roadmap.md`, add a short completed bullet under the CLI or Python-source section:

```markdown
- Completed: `wf --local --config <workflow-config>` now composes configured
  neutral server sources in-process instead of falling back to built-in static
  sources only.
```

If a nearby item already describes this exact gap, update that item instead of adding a duplicate.

- [ ] **Step 3: Run docs link smoke if available**

Run:

```bash
uv run pytest tests/docs -q
```

Expected: PASS.

- [ ] **Step 4: Commit docs**

```bash
git add docs/wf_cli.md docs/current_roadmap.md
git commit -m "docs: clarify local cli config composition"
```

---

### Task 5: Final Verification

**Files:**
- Verify only; no new code expected.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/wf_cli/test_context.py tests/wf_cli/test_remote_target.py tests/docs -q
```

Expected: PASS.

- [ ] **Step 2: Run lint on touched files**

Run:

```bash
uv run ruff check src/wf_cli/context.py tests/wf_cli/test_context.py tests/wf_cli/test_remote_target.py
```

Expected: `All checks passed!`

- [ ] **Step 3: Run formatter check on touched files**

Run:

```bash
uv run ruff format --check src/wf_cli/context.py tests/wf_cli/test_context.py tests/wf_cli/test_remote_target.py
```

Expected: files already formatted.

- [ ] **Step 4: Run typecheck on touched Python files**

Run:

```bash
uv run basedpyright --level error src/wf_cli/context.py tests/wf_cli/test_context.py tests/wf_cli/test_remote_target.py
```

Expected: 0 errors.

- [ ] **Step 5: Inspect final diff**

Run:

```bash
git diff --stat HEAD
git diff --check
```

Expected: only intended files changed; no whitespace errors. CRLF warnings on Windows are acceptable if they match existing repo behavior.

---

## Self-Review

- Spec coverage: The plan covers the specific bug: `--local --config` should use configured server sources, not static-only server construction. It also preserves `--url` and legacy config behavior by not touching those branches.
- Placeholder scan: No `TBD`, generic "handle edge cases", or missing code snippets remain.
- Type consistency: The plan uses existing `load_cli_context`, `build_workflow_server_from_workflow_config`, `list_capabilities(source_id=..., limit=...)`, and capability response key `name`, matching current code/test conventions.
