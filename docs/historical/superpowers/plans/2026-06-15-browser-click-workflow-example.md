# Browser Click Workflow Example Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic multi-node workflow example that opens a local browser page with a button, captures before/after snapshots around a simulated or human click, and runs through artifact/deployment/run.

**Architecture:** The example is a trusted Python source under `examples/browser_click_workflow/`. It uses a tiny stdlib HTTP server as the page fixture and three serial workflow nodes: `open_click_page -> wait_for_click -> collect_snapshots`. Tests run with `simulate=true` and `open_browser=false`; manual users can set `open_browser=true`.

**Tech Stack:** Python 3.14, `wf_authoring.node`, `wf_config`, `wf_server.config`, stdlib `http.server`, `threading`, `urllib.request`, pytest.

---

## Boundaries

- Do not implement fork/gather.
- Do not depend on Playwright or Playwright MCP for this committed baseline.
- Do not output base64 screenshots. Snapshots are bounded JSON values: title, status text, button text, clicked flag, event log.
- Any background HTTP server started by the source must be shut down by the final workflow node or explicit helper cleanup.
- The later agent-trial harness may use `npx -y @playwright/mcp@latest`; this example must remain deterministic without it.

## File Structure

- Create `examples/browser_click_workflow/ops.py` — Python source with the three `@node` capabilities and stdlib local page session manager.
- Create `examples/browser_click_workflow/wf.config.json` — local workflow config with `local.browser_click` Python source and RPC transport on an unused example port.
- Create `examples/browser_click_workflow/run-input.json` — deterministic run input using simulated click and no browser popup.
- Create `examples/browser_click_workflow/README.md` — runbook and expected output.
- Create `tests/examples/test_browser_click_workflow_example.py` — helper tests and full artifact/deployment/run lifecycle test.
- Modify `docs/add/system-design-implementation.md` — reference this as optional richer multi-node evidence, without replacing the deterministic report case study.
- Modify `docs/add/evidence-index.md` — add browser click example as supplemental lifecycle/graph evidence.
- Modify `docs/project_map.md` — list the new example.
- Modify `docs/current_roadmap.md` — mark browser-click example completed.

---

### Task 1: Add Browser Click Python Source

**Files:**
- Create: `examples/browser_click_workflow/ops.py`
- Test: `tests/examples/test_browser_click_workflow_example.py`

- [ ] **Step 1: Create failing helper tests**

Create `tests/examples/test_browser_click_workflow_example.py` with:

```python
from __future__ import annotations

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


def test_browser_click_source_simulates_click_and_cleans_up() -> None:
    opened = _open_click_page(
        OpenPageInput(button_label="Launch Workflow", open_browser=False)
    )

    assert opened.before.clicked is False
    assert opened.before.button_text == "Launch Workflow"
    assert opened.before.status_text == "Waiting for click"

    clicked = _wait_for_click(
        WaitForClickInput(session_id=opened.session_id, simulate=True, timeout_seconds=2)
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
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
uv run pytest tests/examples/test_browser_click_workflow_example.py -q
```

Expected: fail because `examples.browser_click_workflow.ops` does not exist.

- [ ] **Step 3: Implement `ops.py`**

Create `examples/browser_click_workflow/ops.py`:

```python
from __future__ import annotations

import json
import threading
import uuid
import webbrowser
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field

from wf_authoring import node


class Snapshot(BaseModel):
    title: str
    url: str
    button_text: str
    status_text: str
    clicked: bool
    events: list[str] = Field(default_factory=list, max_length=10)


class OpenPageInput(BaseModel):
    button_label: str = "Click to continue"
    open_browser: bool = Field(
        default=False,
        description="Open the page in the default browser for manual runs.",
    )


class OpenPageOutput(BaseModel):
    session_id: str
    url: str
    before: Snapshot


class WaitForClickInput(BaseModel):
    session_id: str
    simulate: bool = Field(
        default=True,
        description="When true, perform a deterministic HTTP click instead of waiting.",
    )
    timeout_seconds: float = Field(default=10.0, gt=0)


class WaitForClickOutput(BaseModel):
    clicked: bool
    after: Snapshot


class CollectSnapshotsInput(BaseModel):
    session_id: str
    before: Snapshot
    after: Snapshot


class CollectSnapshotsOutput(BaseModel):
    before: Snapshot
    after: Snapshot
    closed: bool


@dataclass(slots=True)
class _ClickSession:
    session_id: str
    button_label: str
    server: ThreadingHTTPServer
    thread: threading.Thread
    clicked: threading.Event
    events: list[str]

    @property
    def url(self) -> str:
        host, port = self.server.server_address
        return f"http://{host}:{port}/"

    def snapshot(self) -> Snapshot:
        clicked = self.clicked.is_set()
        return Snapshot(
            title="Workflow Click Fixture",
            url=self.url,
            button_text=self.button_label,
            status_text="Button clicked" if clicked else "Waiting for click",
            clicked=clicked,
            events=list(self.events[-10:]),
        )

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


_SESSIONS: dict[str, _ClickSession] = {}
_SESSIONS_LOCK = threading.Lock()


class _ClickHandler(BaseHTTPRequestHandler):
    server: _ClickServer

    def log_message(self, _format: str, *_args: object) -> None:
        """Keep example runs quiet; workflow trace carries the useful output."""

    def do_GET(self) -> None:
        if self.path == "/":
            self._send_html()
            return
        if self.path == "/snapshot":
            self._send_json(self.server.session.snapshot().model_dump(mode="json"))
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path != "/click":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        session = self.server.session
        session.clicked.set()
        session.events.append("click")
        self._send_json(session.snapshot().model_dump(mode="json"))

    def _send_html(self) -> None:
        session = self.server.session
        status = "Button clicked" if session.clicked.is_set() else "Waiting for click"
        html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Workflow Click Fixture</title>
  <style>
    body {{ font-family: Georgia, serif; margin: 3rem; background: #f8f3e8; color: #1f2933; }}
    main {{ max-width: 720px; padding: 2rem; border: 3px solid #1f2933; background: #fffaf0; }}
    button {{ font-size: 1.25rem; padding: 0.9rem 1.3rem; border: 2px solid #1f2933; background: #f2b84b; cursor: pointer; }}
    #status {{ margin-top: 1rem; font-weight: 700; }}
  </style>
</head>
<body>
  <main>
    <h1>Workflow Click Fixture</h1>
    <button id="continue" type="button">{session.button_label}</button>
    <p id="status">{status}</p>
  </main>
  <script>
    document.getElementById("continue").addEventListener("click", async () => {{
      await fetch("/click", {{ method: "POST" }});
      document.getElementById("status").textContent = "Button clicked";
    }});
  </script>
</body>
</html>"""
        encoded = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_json(self, payload: dict[str, object]) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


class _ClickServer(ThreadingHTTPServer):
    session: _ClickSession
    allow_reuse_address: ClassVar[bool] = True


@node(name="open_click_page")
def open_click_page(payload: OpenPageInput) -> OpenPageOutput:
    return _open_click_page(payload)


@node(name="wait_for_click")
def wait_for_click(payload: WaitForClickInput) -> WaitForClickOutput:
    return _wait_for_click(payload)


@node(name="collect_snapshots")
def collect_snapshots(payload: CollectSnapshotsInput) -> CollectSnapshotsOutput:
    return _collect_snapshots(payload)


def _open_click_page(payload: OpenPageInput) -> OpenPageOutput:
    session_id = f"click_{uuid.uuid4().hex}"
    server = _ClickServer(("127.0.0.1", 0), _ClickHandler)
    session = _ClickSession(
        session_id=session_id,
        button_label=payload.button_label,
        server=server,
        thread=threading.Thread(target=server.serve_forever, daemon=True),
        clicked=threading.Event(),
        events=["opened"],
    )
    server.session = session
    with _SESSIONS_LOCK:
        _SESSIONS[session_id] = session
    session.thread.start()
    if payload.open_browser:
        webbrowser.open(session.url)
    return OpenPageOutput(
        session_id=session_id,
        url=session.url,
        before=session.snapshot(),
    )


def _wait_for_click(payload: WaitForClickInput) -> WaitForClickOutput:
    session = _get_session(payload.session_id)
    if payload.simulate:
        request = Request(f"{session.url}click", method="POST")
        with urlopen(request, timeout=payload.timeout_seconds) as response:
            response.read()
    elif not session.clicked.wait(timeout=payload.timeout_seconds):
        raise TimeoutError("timed out waiting for click")
    return WaitForClickOutput(clicked=session.clicked.is_set(), after=session.snapshot())


def _collect_snapshots(payload: CollectSnapshotsInput) -> CollectSnapshotsOutput:
    session = _get_session(payload.session_id)
    session.close()
    with _SESSIONS_LOCK:
        _SESSIONS.pop(payload.session_id, None)
    return CollectSnapshotsOutput(before=payload.before, after=payload.after, closed=True)


def _get_session(session_id: str) -> _ClickSession:
    with _SESSIONS_LOCK:
        session = _SESSIONS.get(session_id)
    if session is None:
        raise ValueError(f"unknown click session {session_id!r}")
    return session


def _active_session_count() -> int:
    with _SESSIONS_LOCK:
        return len(_SESSIONS)


registry = [open_click_page, wait_for_click, collect_snapshots]
```

- [ ] **Step 4: Run helper tests**

Run:

```powershell
uv run pytest tests/examples/test_browser_click_workflow_example.py::test_browser_click_source_simulates_click_and_cleans_up tests/examples/test_browser_click_workflow_example.py::test_browser_click_source_human_timeout_cleans_up -q
```

Expected: both tests pass.

- [ ] **Step 5: Commit**

```powershell
git add examples/browser_click_workflow/ops.py tests/examples/test_browser_click_workflow_example.py
git commit -m "feat: add browser click source example"
```

---

### Task 2: Add Config, Input, And Multi-Node Lifecycle Test

**Files:**
- Create: `examples/browser_click_workflow/wf.config.json`
- Create: `examples/browser_click_workflow/run-input.json`
- Modify: `tests/examples/test_browser_click_workflow_example.py`

- [ ] **Step 1: Create config**

Create `examples/browser_click_workflow/wf.config.json`:

```json
{
  "version": 1,
  "client": {
    "target": {
      "kind": "rpc_http",
      "url": "http://127.0.0.1:8772/rpc",
      "timeout_seconds": 30
    }
  },
  "server": {
    "store": {
      "kind": "filesystem",
      "root": ".wf_browser_click_store"
    },
    "transports": [
      {
        "kind": "rpc_http",
        "host": "127.0.0.1",
        "port": 8772,
        "path": "/rpc"
      }
    ],
    "sources": [
      {
        "kind": "python",
        "id": "local.browser_click",
        "path": ".",
        "module": "ops",
        "registry": "registry"
      }
    ]
  }
}
```

- [ ] **Step 2: Create deterministic run input**

Create `examples/browser_click_workflow/run-input.json`:

```json
{
  "button_label": "Launch Workflow",
  "open_browser": false,
  "simulate": true,
  "timeout_seconds": 2
}
```

- [ ] **Step 3: Add full lifecycle test**

Append to `tests/examples/test_browser_click_workflow_example.py`:

```python
from pathlib import Path

from wf_config import load_workflow_config
from wf_server.config import build_workflow_server_from_workflow_config


EXAMPLE_DIR = Path(__file__).resolve().parents[2] / "examples" / "browser_click_workflow"


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
```

- [ ] **Step 4: Run lifecycle test**

Run:

```powershell
uv run pytest tests/examples/test_browser_click_workflow_example.py -q
```

Expected: all browser-click tests pass.

- [ ] **Step 5: Validate config**

Run:

```powershell
uv run wf config validate examples/browser_click_workflow/wf.config.json
```

Expected: valid config output.

- [ ] **Step 6: Commit**

```powershell
git add examples/browser_click_workflow/wf.config.json examples/browser_click_workflow/run-input.json tests/examples/test_browser_click_workflow_example.py
git commit -m "test: prove browser click workflow lifecycle"
```

---

### Task 3: Add Runbook And Documentation Links

**Files:**
- Create: `examples/browser_click_workflow/README.md`
- Modify: `docs/add/system-design-implementation.md`
- Modify: `docs/add/evidence-index.md`
- Modify: `docs/project_map.md`
- Modify: `docs/current_roadmap.md`

- [ ] **Step 1: Create README**

Create `examples/browser_click_workflow/README.md`:

````markdown
# Browser Click Workflow Example

This example demonstrates a serial multi-node workflow over a trusted Python
source:

```text
open_click_page -> wait_for_click -> collect_snapshots
```

It opens a local HTML page with one visible button, captures a bounded JSON
snapshot before the click, performs a deterministic simulated click by default,
captures an after snapshot, closes the local server, and returns both snapshots
as workflow output.

The example deliberately avoids browser screenshots and base64 payloads. The
snapshots are small JSON objects suitable for CLI and LLM-agent output.

## Run

From the repository root:

```powershell
uv run wf config validate examples/browser_click_workflow/wf.config.json
uv run wf-rpc-server --config examples/browser_click_workflow/wf.config.json
```

In another terminal:

```powershell
uv run wf --config examples/browser_click_workflow/wf.config.json status
uv run wf --config examples/browser_click_workflow/wf.config.json cap list --source local.browser_click
```

The full artifact/deployment/run lifecycle is covered by:

```powershell
uv run pytest tests/examples/test_browser_click_workflow_example.py -q
```

## Manual Browser Mode

The checked-in test uses `"simulate": true` and `"open_browser": false`.
For manual experimentation, set `"open_browser": true` in the run input and
use `"simulate": false`; then click the button before `timeout_seconds` elapses.
Any browser or local server opened by the source is closed by the final
`collect_snapshots` node.
````

- [ ] **Step 2: Link docs**

Patch docs:

- In `docs/project_map.md`, add `examples/browser_click_workflow/` to the examples list as the serial browser-click workflow example.
- In `docs/add/evidence-index.md`, add a supplemental evidence bullet under Python/source or workflow lifecycle evidence:

```markdown
- `examples/browser_click_workflow/`
- `tests/examples/test_browser_click_workflow_example.py`
```

- In `docs/add/system-design-implementation.md`, add one sentence after the report workflow case-study scope paragraph:

```markdown
A supplemental browser-click example demonstrates a serial three-node workflow
with bounded before/after snapshots; it is supporting evidence, not the main
case study.
```

- In `docs/current_roadmap.md`, add a short completed milestone:

```markdown
- Completed supplemental browser-click workflow example with serial multi-node lifecycle evidence.
```

- [ ] **Step 3: Run docs checks**

Run:

```powershell
uv run pytest tests/docs -q
```

Expected: pass.

- [ ] **Step 4: Run focused verification**

Run:

```powershell
uv run pytest tests/examples/test_browser_click_workflow_example.py tests/docs -q
uv run ruff check examples/browser_click_workflow tests/examples/test_browser_click_workflow_example.py
uv run basedpyright --level error examples/browser_click_workflow tests/examples/test_browser_click_workflow_example.py
git diff --check
```

Expected:

- Tests pass.
- Ruff has no errors.
- Basedpyright has no errors.
- `git diff --check` reports no whitespace errors except acceptable CRLF warnings on Windows.

- [ ] **Step 5: Commit**

```powershell
git add examples/browser_click_workflow docs/add/system-design-implementation.md docs/add/evidence-index.md docs/project_map.md docs/current_roadmap.md tests/examples/test_browser_click_workflow_example.py
git commit -m "docs: add browser click workflow example"
```

---

## Self-Review Notes

- The example is serial multi-node, not fork/gather.
- The source closes its server in `collect_snapshots`.
- The test uses simulated click and does not open the user's browser.
- The README warns about manual browser mode and cleanup.
- Playwright MCP is intentionally excluded from this baseline; it belongs in a later agent-trial harness plan.
