# RPC Plan Artifact And Staged Agent Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let remote/CLI users create workflow artifacts from declarative JSON/YAML plans, then make the opencode browser-click challenge stage a real `wf-rpc-server` and give the agent a ready `wf --url` target.

**Architecture:** Add a protocol-neutral operation already present in local `WorkflowApi` to the JSON-RPC transport and CLI: `workflow.artifacts.create_from_plan` / `wf artifact create-from-plan`. Then update the agent challenge harness so it starts `wf-rpc-server --config examples/browser_click_workflow/wf.config.json` on a free port, waits for `wf status`, injects that URL into the prompt, runs opencode, and tears the server down.

**Tech Stack:** Python stdlib, Typer, PyYAML, httpx JSON-RPC tests, existing `wf_server`/`wf_transport_rpc_http` test fixtures, opencode CLI harness.

---

## File Structure

- Modify `src/wf_transport_rpc_http/models.py`
  - Add `CreateArtifactFromPlanParams`.
- Modify `src/wf_transport_rpc_http/methods/artifacts.py`
  - Register `workflow.artifacts.create_from_plan`.
- Modify `src/wf_transport_rpc_http/client/artifacts.py`
  - Add `create_artifact_from_plan(...)`.
- Modify `src/wf_cli/io.py`
  - Add `parse_structured_file(path: Path) -> dict[str, Any]` for JSON/YAML object files.
- Modify `src/wf_cli/commands/artifacts.py`
  - Add `wf artifact create-from-plan PLAN_FILE --artifact ...`.
- Modify `tests/wf_transport_rpc_http/test_app.py`
  - Add RPC method test.
- Modify `tests/wf_transport_rpc_http/test_client.py`
  - Add client method test.
- Modify `tests/wf_cli/test_artifacts.py`
  - Add CLI command tests.
- Modify `examples/agent_challenges/browser_click_challenge/run_opencode_trials.py`
  - Add staged server lifecycle and prompt rendering.
- Modify `examples/agent_challenges/browser_click_challenge/prompt.md`
  - Add template tokens for `{{rpc_url}}` and `{{wf_command_prefix}}`.
- Modify `examples/agent_challenges/browser_click_challenge/README.md`
  - Document staged server behavior.
- Modify `tests/examples/test_opencode_browser_click_challenge.py`
  - Add server command/prompt rendering tests.
- Modify `docs/current_roadmap.md`
  - Mark both gaps completed.

---

## Task 1: Add JSON-RPC `create_from_plan`

**Files:**
- Modify: `src/wf_transport_rpc_http/models.py`
- Modify: `src/wf_transport_rpc_http/methods/artifacts.py`
- Modify: `src/wf_transport_rpc_http/client/artifacts.py`
- Test: `tests/wf_transport_rpc_http/test_app.py`
- Test: `tests/wf_transport_rpc_http/test_client.py`

- [ ] **Step 1: Add failing RPC app test**

Add to `tests/wf_transport_rpc_http/test_app.py`:

```python
async def test_rpc_create_artifact_from_plan(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await _rpc(
            client,
            "workflow.artifacts.create_from_plan",
            {
                "artifact_id": "rpc_plan",
                "version": 1,
                "title": "RPC Plan",
                "plan": _constant_plan().model_dump(mode="json"),
                "outcomes": ["ok"],
                "source_bindings": {},
            },
        )
        inspected = await _rpc(
            client,
            "workflow.artifacts.inspect",
            {"artifact_id": "rpc_plan", "version": 1},
        )

    assert created["result"]["artifact_id"] == "rpc_plan"
    assert created["result"]["version"] == 1
    assert inspected["result"]["id"] == "rpc_plan"
    assert inspected["result"]["plan"]["name"] == "client_constant"
```

- [ ] **Step 2: Add failing RPC client test**

Add to `tests/wf_transport_rpc_http/test_client.py`:

```python
async def test_rpc_client_creates_artifact_from_plan(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as http_client:
        client = RpcWorkflowApiClient(
            url="http://test/rpc",
            timeout_seconds=5,
            http_client=http_client,
        )
        created = await client.create_artifact_from_plan(
            artifact_id="client_plan",
            version=1,
            title="Client Plan",
            plan=_constant_plan().model_dump(mode="json"),
            outcomes=("ok",),
            source_bindings={},
        )
        inspected = await client.inspect_artifact(
            artifact_id="client_plan",
            version=1,
        )

    assert created["artifact_id"] == "client_plan"
    assert inspected["id"] == "client_plan"
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```powershell
uv run pytest tests/wf_transport_rpc_http/test_app.py::test_rpc_create_artifact_from_plan tests/wf_transport_rpc_http/test_client.py::test_rpc_client_creates_artifact_from_plan -q
```

Expected: FAIL because `workflow.artifacts.create_from_plan` and the client method do not exist.

- [ ] **Step 4: Add params model**

In `src/wf_transport_rpc_http/models.py`, add after `SaveArtifactParams`:

```python
class CreateArtifactFromPlanParams(RpcParamsModel):
    artifact_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    title: str = Field(min_length=1)
    plan: dict[str, Any]
    outcomes: list[str]
    kind: Literal["workflow", "wrapper"] = "workflow"
    description: str | None = None
    required_capabilities: dict[str, dict[str, Any]] | None = None
    source_bindings: dict[str, str] | None = None
    created_from_catalog_version: str | None = None
```

- [ ] **Step 5: Register RPC method**

In `src/wf_transport_rpc_http/methods/artifacts.py`, import `CreateArtifactFromPlanParams` and add before `workflow.artifacts.save`:

```python
    @entrypoint.method(
        name="workflow.artifacts.create_from_plan",
        errors=[WorkflowRpcError],
    )
    async def workflow_artifacts_create_from_plan(
        params: CreateArtifactFromPlanParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await server.api.create_artifact_from_plan(
                artifact_id=params.artifact_id,
                version=params.version,
                title=params.title,
                plan=params.plan,
                outcomes=tuple(params.outcomes),
                kind=params.kind,
                description=params.description,
                required_capabilities=params.required_capabilities,
                source_bindings=params.source_bindings,
                created_from_catalog_version=params.created_from_catalog_version,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)
```

- [ ] **Step 6: Add RPC client method**

In `src/wf_transport_rpc_http/client/artifacts.py`, import `Sequence` and add:

```python
    async def create_artifact_from_plan(
        self: RpcCaller,
        *,
        artifact_id: str,
        version: int,
        title: str,
        plan: dict[str, Any],
        outcomes: Sequence[str],
        kind: Literal["workflow", "wrapper"] = "workflow",
        description: str | None = None,
        required_capabilities: dict[str, dict[str, Any]] | None = None,
        source_bindings: dict[str, str] | None = None,
        created_from_catalog_version: str | None = None,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.artifacts.create_from_plan",
            {
                "artifact_id": artifact_id,
                "version": version,
                "title": title,
                "plan": plan,
                "outcomes": list(outcomes),
                "kind": kind,
                "description": description,
                "required_capabilities": required_capabilities,
                "source_bindings": source_bindings,
                "created_from_catalog_version": created_from_catalog_version,
            },
        )
```

- [ ] **Step 7: Run tests**

Run:

```powershell
uv run pytest tests/wf_transport_rpc_http/test_app.py::test_rpc_create_artifact_from_plan tests/wf_transport_rpc_http/test_client.py::test_rpc_client_creates_artifact_from_plan -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

Run:

```powershell
git add src\wf_transport_rpc_http\models.py src\wf_transport_rpc_http\methods\artifacts.py src\wf_transport_rpc_http\client\artifacts.py tests\wf_transport_rpc_http\test_app.py tests\wf_transport_rpc_http\test_client.py
git commit -m "feat: expose create artifact from plan over rpc"
```

---

## Task 2: Add `wf artifact create-from-plan`

**Files:**
- Modify: `src/wf_cli/io.py`
- Modify: `src/wf_cli/commands/artifacts.py`
- Test: `tests/wf_cli/test_artifacts.py`

- [ ] **Step 1: Add failing CLI tests**

Extend `_ArtifactHandlers` in `tests/wf_cli/test_artifacts.py`:

```python
    async def create_artifact_from_plan(
        self,
        *,
        artifact_id: str,
        version: int,
        title: str,
        plan: dict[str, Any],
        outcomes: tuple[str, ...],
        kind: str = "workflow",
        description: str | None = None,
        required_capabilities: dict[str, dict[str, Any]] | None = None,
        source_bindings: dict[str, str] | None = None,
        created_from_catalog_version: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append((artifact_id, version))
        return {
            "artifact_id": artifact_id,
            "version": version,
            "title": title,
            "plan_name": plan["name"],
            "outcomes": list(outcomes),
            "kind": kind,
            "source_bindings": source_bindings,
        }
```

Add tests:

```python
def test_artifact_create_from_plan_reads_yaml(monkeypatch, tmp_path) -> None:
    handlers = _ArtifactHandlers()
    monkeypatch.setattr(
        "wf_cli.commands.artifacts.load_cli_context",
        lambda _ctx: _Context(handlers=handlers),
    )
    plan_file = tmp_path / "plan.yaml"
    plan_file.write_text(
        """
name: yaml_plan
input_schema: {type: object, properties: {}}
state_schema: {type: object, properties: {}}
output_schema: {type: object, properties: {}}
outcomes: [ok]
start: __end__
nodes: []
edges: []
""",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "artifact",
            "create-from-plan",
            str(plan_file),
            "--artifact",
            "yaml_artifact",
            "--version",
            "1",
            "--title",
            "YAML Artifact",
            "--outcome",
            "ok",
            "--binding",
            "local.ops=local.ops",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["artifact_id"] == "yaml_artifact"
    assert payload["plan_name"] == "yaml_plan"
    assert payload["source_bindings"] == {"local.ops": "local.ops"}


def test_artifact_create_from_plan_rejects_non_object_yaml(monkeypatch, tmp_path) -> None:
    handlers = _ArtifactHandlers()
    monkeypatch.setattr(
        "wf_cli.commands.artifacts.load_cli_context",
        lambda _ctx: _Context(handlers=handlers),
    )
    plan_file = tmp_path / "plan.yaml"
    plan_file.write_text("- not\n- object\n", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "artifact",
            "create-from-plan",
            str(plan_file),
            "--artifact",
            "bad",
            "--version",
            "1",
            "--title",
            "Bad",
        ],
    )

    assert result.exit_code != 0
    assert "structured file must contain an object" in result.output.lower()
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
uv run pytest tests/wf_cli/test_artifacts.py -q
```

Expected: FAIL because the command/helper do not exist.

- [ ] **Step 3: Add structured file parser**

In `src/wf_cli/io.py`, import `yaml` and add:

```python
import yaml
```

Add:

```python
def parse_structured_file(path: Path) -> dict[str, Any]:
    """Parse one JSON/YAML object file for declarative workflow inputs."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CliInputError(f"could not read file {path!s}: {exc}") from exc
    try:
        payload = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise CliInputError(f"invalid YAML/JSON file {path!s}: {exc}") from exc
    if not isinstance(payload, dict):
        raise CliInputError("structured file must contain an object")
    return payload
```

- [ ] **Step 4: Add CLI command**

In `src/wf_cli/commands/artifacts.py`, import `Path`, `parse_structured_file`, and add before `delete`:

```python
@app.command("create-from-plan")
def create_artifact_from_plan(
    ctx: typer.Context,
    plan_file: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    artifact_id: Annotated[str, typer.Option("--artifact", help="Artifact id.")],
    version: Annotated[int, typer.Option("--version", min=1, help="Artifact version.")],
    title: Annotated[str, typer.Option("--title", help="Artifact title.")],
    outcome: Annotated[
        list[str] | None,
        typer.Option("--outcome", help="Artifact outcome. Repeatable."),
    ] = None,
    kind: Annotated[
        Literal["workflow", "wrapper"], typer.Option("--kind", help="Artifact kind.")
    ] = "workflow",
    description: Annotated[
        str | None, typer.Option("--description", help="Artifact description.")
    ] = None,
    binding: Annotated[
        list[str] | None,
        typer.Option("--binding", help="Logical=concrete source binding. Repeatable."),
    ] = None,
) -> None:
    """Create an artifact from a raw JSON/YAML workflow plan file."""
    try:
        plan = parse_structured_file(plan_file)
        source_bindings = parse_bindings(binding or [])
    except CliInputError as exc:
        raise typer.BadParameter(str(exc)) from exc
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.create_artifact_from_plan(
                artifact_id=artifact_id,
                version=version,
                title=title,
                plan=plan,
                outcomes=tuple(outcome or ["ok"]),
                kind=kind,
                description=description,
                source_bindings=source_bindings or None,
            ),
        )
    )
```

- [ ] **Step 5: Run tests**

Run:

```powershell
uv run pytest tests/wf_cli/test_artifacts.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```powershell
git add src\wf_cli\io.py src\wf_cli\commands\artifacts.py tests\wf_cli\test_artifacts.py
git commit -m "feat: add artifact create-from-plan cli"
```

---

## Task 3: Stage RPC Server In Opencode Harness

**Files:**
- Modify: `examples/agent_challenges/browser_click_challenge/run_opencode_trials.py`
- Modify: `examples/agent_challenges/browser_click_challenge/prompt.md`
- Modify: `examples/agent_challenges/browser_click_challenge/README.md`
- Test: `tests/examples/test_opencode_browser_click_challenge.py`

- [ ] **Step 1: Add failing harness tests**

Add imports in `tests/examples/test_opencode_browser_click_challenge.py`:

```python
from examples.agent_challenges.browser_click_challenge.run_opencode_trials import (
    render_prompt,
    server_command,
)
```

Add tests:

```python
def test_render_prompt_injects_rpc_url_and_command_prefix(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text(
        "Use {{rpc_url}} with {{wf_command_prefix}}",
        encoding="utf-8",
    )

    rendered = render_prompt(
        prompt,
        rpc_url="http://127.0.0.1:8765/rpc",
    )

    assert "http://127.0.0.1:8765/rpc" in rendered
    assert "uv run wf --url http://127.0.0.1:8765/rpc" in rendered


def test_server_command_uses_example_config_and_requested_port() -> None:
    command = server_command(port=8765)

    assert command[:3] == ["uv", "run", "wf-rpc-server"]
    assert "--config" in command
    assert "examples/browser_click_workflow/wf.config.json" in command
    assert "--port" in command
    assert "8765" in command
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
uv run pytest tests/examples/test_opencode_browser_click_challenge.py -q
```

Expected: FAIL because `render_prompt` and `server_command` do not exist.

- [ ] **Step 3: Add prompt template tokens**

In `examples/agent_challenges/browser_click_challenge/prompt.md`, replace the product-path paragraph with:

```markdown
A workflow RPC server is already running at:

```text
{{rpc_url}}
```

Use this command prefix for product-facing operations:

```powershell
{{wf_command_prefix}}
```

Use this repository's workflow product path. That means you should use the
`wf` CLI against the provided URL, create or reuse a workflow deployment, and
run the deployment through the workflow API. Do not solve the challenge with
only a standalone Playwright/Python script.
```

- [ ] **Step 4: Implement prompt rendering and server command**

In `examples/agent_challenges/browser_click_challenge/run_opencode_trials.py`, add:

```python
DEFAULT_SERVER_PORT = 8772
EXAMPLE_CONFIG = ROOT / "examples" / "browser_click_workflow" / "wf.config.json"
```

Add:

```python
def rpc_url_for_port(port: int) -> str:
    return f"http://127.0.0.1:{port}/rpc"


def server_command(*, port: int) -> list[str]:
    return [
        "uv",
        "run",
        "wf-rpc-server",
        "--config",
        str(EXAMPLE_CONFIG.relative_to(ROOT)).replace("\\", "/"),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]


def render_prompt(prompt_path: Path, *, rpc_url: str) -> str:
    command_prefix = f"uv run wf --url {rpc_url}"
    return (
        prompt_path.read_text(encoding="utf-8")
        .replace("{{rpc_url}}", rpc_url)
        .replace("{{wf_command_prefix}}", command_prefix)
    )
```

Change `build_opencode_command` to call `render_prompt(config.prompt_path, rpc_url=config.rpc_url)`. Add `rpc_url: str` to `TrialConfig`.

- [ ] **Step 5: Add managed server lifecycle**

Add:

```python
@dataclass(slots=True)
class ManagedServer:
    process: subprocess.Popen[str]
    rpc_url: str


def start_server(*, port: int, timeout_seconds: int = 30) -> ManagedServer:
    command = server_command(port=port)
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    rpc_url = rpc_url_for_port(port)
    try:
        wait_for_status(rpc_url=rpc_url, timeout_seconds=timeout_seconds)
    except Exception:
        stop_server(process)
        raise
    return ManagedServer(process=process, rpc_url=rpc_url)


def wait_for_status(*, rpc_url: str, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    command = ["uv", "run", "wf", "--url", rpc_url, "status"]
    last_stderr = ""
    while time.monotonic() < deadline:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode == 0:
            return
        last_stderr = completed.stderr
        time.sleep(0.5)
    raise RuntimeError(f"wf status did not become ready: {last_stderr}")


def stop_server(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
```

Import `sys`. Add CLI flags:

```python
parser.add_argument("--server-url", default=None)
parser.add_argument("--start-server", action="store_true", default=True)
parser.add_argument("--no-start-server", action="store_false", dest="start_server")
parser.add_argument("--server-port", type=int, default=DEFAULT_SERVER_PORT)
```

In `main`, if `args.server_url` is set, use it. Else if `args.start_server`, call `start_server(port=args.server_port)` and stop it in `finally`. Else use `rpc_url_for_port(args.server_port)` and do not start/stop.

- [ ] **Step 6: Update README**

Document default behavior:

```markdown
By default the harness starts:

```powershell
uv run wf-rpc-server --config examples/browser_click_workflow/wf.config.json --host 127.0.0.1 --port 8772
```

It waits until:

```powershell
uv run wf --url http://127.0.0.1:8772/rpc status
```

passes, injects that URL into the prompt, runs opencode, then stops the server.
Use `--server-url` to target an already-running server or `--no-start-server` to
skip lifecycle management.
```

- [ ] **Step 7: Run tests**

Run:

```powershell
uv run pytest tests/examples/test_opencode_browser_click_challenge.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

Run:

```powershell
git add examples\agent_challenges\browser_click_challenge\run_opencode_trials.py examples\agent_challenges\browser_click_challenge\prompt.md examples\agent_challenges\browser_click_challenge\README.md tests\examples\test_opencode_browser_click_challenge.py
git commit -m "feat: stage rpc server for opencode challenge"
```

---

## Task 4: Docs And Final Verification

**Files:**
- Modify: `docs/current_roadmap.md`
- Move: this plan to `docs/historical/superpowers/plans/2026-06-15-rpc-plan-artifact-and-staged-agent-harness.md`

- [ ] **Step 1: Update roadmap**

Add under Priority 1:

```markdown
- Completed: raw JSON/YAML workflow plans can be turned into artifacts through
  JSON-RPC and `wf artifact create-from-plan`, allowing agent/evidence harnesses
  to use the product-facing CLI path.
- Completed: the opencode browser-click challenge harness stages a real
  `wf-rpc-server`, injects the RPC URL into the prompt, and tears the server
  down after trials.
```

- [ ] **Step 2: Archive plan**

Run:

```powershell
Move-Item -LiteralPath docs\superpowers\plans\2026-06-15-rpc-plan-artifact-and-staged-agent-harness.md -Destination docs\historical\superpowers\plans\2026-06-15-rpc-plan-artifact-and-staged-agent-harness.md
```

- [ ] **Step 3: Final verification**

Run:

```powershell
uv run pytest tests/wf_transport_rpc_http/test_app.py::test_rpc_create_artifact_from_plan tests/wf_transport_rpc_http/test_client.py::test_rpc_client_creates_artifact_from_plan tests/wf_cli/test_artifacts.py tests/examples/test_opencode_browser_click_challenge.py tests/docs -q
uv run ruff check src/wf_transport_rpc_http/models.py src/wf_transport_rpc_http/methods/artifacts.py src/wf_transport_rpc_http/client/artifacts.py src/wf_cli/io.py src/wf_cli/commands/artifacts.py examples/agent_challenges/browser_click_challenge tests/wf_cli/test_artifacts.py tests/examples/test_opencode_browser_click_challenge.py tests/docs
uv run basedpyright --level error src/wf_transport_rpc_http/models.py src/wf_transport_rpc_http/methods/artifacts.py src/wf_transport_rpc_http/client/artifacts.py src/wf_cli/io.py src/wf_cli/commands/artifacts.py examples/agent_challenges/browser_click_challenge tests/wf_cli/test_artifacts.py tests/examples/test_opencode_browser_click_challenge.py tests/docs
```

Expected:
- pytest passes.
- ruff passes.
- basedpyright reports 0 errors.

- [ ] **Step 4: Commit**

Run:

```powershell
git add docs\current_roadmap.md docs\historical\superpowers\plans\2026-06-15-rpc-plan-artifact-and-staged-agent-harness.md
git commit -m "docs: record staged agent challenge harness"
```

---

## Manual Trial After Implementation

Run:

```powershell
uv run python examples/agent_challenges/browser_click_challenge/run_opencode_trials.py `
  --model opencode/mimo-v2.5-free `
  --variant high `
  --trials 1 `
  --timeout-seconds 900
```

Expected:
- Harness starts `wf-rpc-server`.
- Prompt includes `uv run wf --url http://127.0.0.1:8772/rpc`.
- Agent final answer includes YAML `challenge_report`.
- Trial JSON classification is one of `success`, `workflow_script`, `run_failed`, `workflow_not_used`, `parse_error`, `timeout`, or `unknown`.

---

## Self-Review Checklist

- JSON-RPC exposes the same artifact-from-plan operation local `WorkflowApi` already has.
- CLI supports JSON and YAML plan files.
- Harness does not require the agent to start the server.
- Harness prompt includes the actual RPC URL.
- Harness still supports `--server-url` for manually staged servers.
- Tests do not invoke opencode.
- Tests do not depend on a live network server except through local ASGI transports.
