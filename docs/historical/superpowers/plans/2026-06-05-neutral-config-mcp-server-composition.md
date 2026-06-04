# Neutral Config MCP Server Composition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let `wf-rpc-server --config <workflow-config.json>` build an MCP-backed `WorkflowServer` when neutral `wf_config.server.sources[]` contains `kind: "mcp"` entries.

**Architecture:** Keep JSON-RPC app/client/method modules transport-only. The CLI may load neutral `wf_config`; MCP-specific conversion stays in `wf_mcp`. This plan assumes the prior plan has added `wf_config.McpSourceConfig`, `StdioSourceTransportConfig`, and `HttpSourceTransportConfig`.

**Tech Stack:** Pydantic config models, `wf_mcp.broker.config`, `wf_mcp.source_registry`, Typer CLI tests, ASGITransport JSON-RPC tests.

---

## File Structure

- Modify `src/wf_mcp/broker/config.py`: add conversion from neutral `WorkflowConfigFile` into `BrokerConfig`.
- Modify `src/wf_mcp/source_registry.py`: add conversion from neutral `McpSourceConfig` to `McpSourceRegistryEntry` or `ConnectionConfig`.
- Modify `src/wf_transport_rpc_http/cli.py`: when `--config` has MCP sources, build MCP-backed server from neutral config instead of requiring `--mcp-config`.
- Modify `tests/wf_mcp/server/test_config.py` or create `tests/wf_mcp/test_workflow_config_bridge.py`: test neutral config conversion into broker runtime.
- Modify `tests/wf_transport_rpc_http/test_cli.py`: test `wf-rpc-server --config` selects MCP-backed server for neutral MCP source config.
- Modify docs to mark this slice complete.

## Preconditions

This plan assumes these names exist from the prior plan:

```python
from wf_config import (
    HttpSourceTransportConfig,
    McpSourceConfig,
    StdioSourceTransportConfig,
    WorkflowConfigFile,
)
```

Do not start this plan until `uv run pytest tests/wf_config/test_config_models.py -q` passes.

## Task 1: Test Neutral Config to BrokerConfig Conversion

**Files:**
- Create: `tests/wf_mcp/test_workflow_config_bridge.py`

- [ ] **Step 1: Create test file**

Create `tests/wf_mcp/test_workflow_config_bridge.py`:

```python
from __future__ import annotations

from wf_config import WorkflowConfigFile
from wf_mcp.broker.config import broker_config_from_workflow_config


def test_broker_config_from_workflow_config_converts_mcp_sources(tmp_path) -> None:
    workflow_config = WorkflowConfigFile.model_validate(
        {
            "version": 1,
            "server": {
                "store": {"kind": "filesystem", "root": str(tmp_path / "store")},
                "sources": [
                    {
                        "kind": "mcp",
                        "id": "everything.default",
                        "enabled": True,
                        "provider": "everything",
                        "account": "default",
                        "profile": "dev",
                        "ownership": "seed",
                        "transport": {
                            "kind": "stdio",
                            "command": "uvx",
                            "args": ["mcp-server-everything"],
                            "env": {"DEBUG": "1"},
                        },
                        "auth_ref": "auth.everything.default",
                        "metadata": {"description": "Everything test server"},
                    }
                ],
            },
        }
    )

    broker_config = broker_config_from_workflow_config(workflow_config)

    assert broker_config.store_root == tmp_path / "store"
    assert len(broker_config.connections) == 1
    connection = broker_config.connections[0]
    assert connection.id == "everything.default"
    assert connection.server == "everything"
    assert connection.account == "default"
    assert connection.enabled is True
    assert connection.source_config_ownership == "seed"
    assert connection.metadata["profile"] == "dev"
    assert connection.metadata["auth_ref"] == "auth.everything.default"
    assert connection.metadata["transport"] == {
        "kind": "stdio",
        "command": "uvx",
        "args": ["mcp-server-everything"],
        "env": {"DEBUG": "1"},
    }
    assert connection.metadata["description"] == "Everything test server"


def test_broker_config_from_workflow_config_ignores_non_mcp_sources(tmp_path) -> None:
    workflow_config = WorkflowConfigFile.model_validate(
        {
            "version": 1,
            "server": {
                "store": {"kind": "filesystem", "root": str(tmp_path / "store")},
                "sources": [{"kind": "stdlib", "id": "wf.std"}],
            },
        }
    )

    broker_config = broker_config_from_workflow_config(workflow_config)

    assert broker_config.store_root == tmp_path / "store"
    assert broker_config.connections == []
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
uv run pytest tests/wf_mcp/test_workflow_config_bridge.py -q
```

Expected: fail because `broker_config_from_workflow_config` does not exist.

## Task 2: Implement Conversion From Neutral Config

**Files:**
- Modify: `src/wf_mcp/source_registry.py`
- Modify: `src/wf_mcp/broker/config.py`

- [ ] **Step 1: Add neutral source conversion helper**

In `src/wf_mcp/source_registry.py`, add under `connection_config_to_registry_entry`:

```python
def workflow_mcp_source_to_connection_config(source: object) -> ConnectionConfig:
    """Convert neutral wf_config MCP source config into a broker connection.

    Keep this adapter in wf_mcp because the output is MCP broker runtime state.
    The input is intentionally typed as object to avoid making wf_mcp's public
    registry module part of wf_config's import graph.
    """
    from .models import ConnectionConfig

    if getattr(source, "kind", None) != "mcp":
        raise ValueError("expected wf_config MCP source")
    transport = getattr(source, "transport")
    metadata = dict(getattr(source, "metadata", {}))
    metadata.update(
        {
            "transport": transport.model_dump(mode="json"),
            "source_registry": False,
        }
    )
    profile = getattr(source, "profile", None)
    if profile is not None:
        metadata["profile"] = profile
    auth_ref = getattr(source, "auth_ref", None)
    if auth_ref is not None:
        metadata["auth_ref"] = auth_ref
    return ConnectionConfig(
        id=getattr(source, "id"),
        server=getattr(source, "provider"),
        account=getattr(source, "account"),
        enabled=getattr(source, "enabled"),
        metadata=metadata,
        source_config_ownership=getattr(source, "ownership"),
    )
```

Add `"workflow_mcp_source_to_connection_config"` to `__all__`.

- [ ] **Step 2: Add broker config bridge**

In `src/wf_mcp/broker/config.py`, add imports:

```python
from wf_config import WorkflowConfigFile
from ..source_registry import FileSourceRegistryStore, workflow_mcp_source_to_connection_config
```

Replace the existing `FileSourceRegistryStore` import line accordingly.

Add after `load_broker_config`:

```python
def broker_config_from_workflow_config(config: WorkflowConfigFile) -> BrokerConfig:
    """Create MCP broker runtime config from neutral workflow server config."""
    return BrokerConfig(
        store_root=config.server.store.root,
        connections=[
            workflow_mcp_source_to_connection_config(source)
            for source in config.server.sources
            if getattr(source, "kind", None) == "mcp"
        ],
    )
```

- [ ] **Step 3: Run conversion test**

Run:

```bash
uv run pytest tests/wf_mcp/test_workflow_config_bridge.py -q
```

Expected: pass.

## Task 3: Build MCP-Backed WorkflowServer From Neutral Config

**Files:**
- Modify: `src/wf_mcp/broker/server.py`
- Modify: `tests/wf_transport_rpc_http/test_cli.py`

- [ ] **Step 1: Add broker server helper**

In `src/wf_mcp/broker/server.py`, import:

```python
from wf_config import WorkflowConfigFile
from .config import broker_config_from_workflow_config
```

Add below `build_workflow_server_from_config`:

```python
def build_workflow_server_from_workflow_config(
    config: WorkflowConfigFile,
) -> WorkflowServer:
    """Build an MCP-backed WorkflowServer from neutral workflow config sources."""
    return build_workflow_server_from_config(
        broker_config_from_workflow_config(config)
    )
```

Add it to `__all__` in this file and `src/wf_mcp/broker/__init__.py`.

- [ ] **Step 2: Add CLI selection test**

In `tests/wf_transport_rpc_http/test_cli.py`, add:

```python
def test_rpc_server_cli_config_with_mcp_source_uses_mcp_builder(
    monkeypatch, tmp_path
) -> None:
    captured = {}

    def fake_build_from_workflow_config(config):
        captured["source_kinds"] = [source.kind for source in config.server.sources]
        return object()

    def fake_create_rpc_app(server, *, rpc_path="/rpc"):
        captured["server"] = server
        captured["rpc_path"] = rpc_path
        return "app"

    def fake_run(app, *, host, port, access_log):
        captured["run"] = {
            "app": app,
            "host": host,
            "port": port,
            "access_log": access_log,
        }

    monkeypatch.setattr(
        "wf_transport_rpc_http.cli.build_workflow_server_from_workflow_config",
        fake_build_from_workflow_config,
    )
    monkeypatch.setattr("wf_transport_rpc_http.cli.create_rpc_app", fake_create_rpc_app)
    monkeypatch.setattr("wf_transport_rpc_http.cli.uvicorn.run", fake_run)

    config_path = tmp_path / "wf.json"
    config_path.write_text(
        """
{
  "version": 1,
  "server": {
    "store": {"kind": "filesystem", "root": ".wf_store"},
    "transports": [{"kind": "rpc_http", "host": "127.0.0.1", "port": 8765}],
    "sources": [
      {
        "kind": "mcp",
        "id": "everything.default",
        "provider": "everything",
        "account": "default",
        "transport": {"kind": "stdio", "command": "uvx"}
      }
    ]
  }
}
""",
        encoding="utf-8",
    )

    from wf_transport_rpc_http.cli import app
    from typer.testing import CliRunner

    result = CliRunner().invoke(app, ["--config", str(config_path)])

    assert result.exit_code == 0, result.output
    assert captured["source_kinds"] == ["mcp"]
    assert captured["run"]["app"] == "app"
```

- [ ] **Step 3: Run test and verify failure**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_cli.py::test_rpc_server_cli_config_with_mcp_source_uses_mcp_builder -q
```

Expected: fail because `wf_transport_rpc_http.cli` does not import or use `build_workflow_server_from_workflow_config`.

## Task 4: Wire RPC Server CLI to Neutral MCP Sources

**Files:**
- Modify: `src/wf_transport_rpc_http/cli.py`

- [ ] **Step 1: Import the new builder**

Update the MCP import line:

```python
from wf_mcp.broker import (
    build_workflow_server_from_config,
    build_workflow_server_from_workflow_config,
    load_broker_config,
)
```

- [ ] **Step 2: Select MCP builder when neutral config has MCP sources**

Inside the `if config is not None:` block, after `workflow_config = load_workflow_config(config)`, add:

```python
        has_mcp_sources = any(
            getattr(source, "kind", None) == "mcp"
            for source in workflow_config.server.sources
        )
        if server is None and has_mcp_sources:
            server = build_workflow_server_from_workflow_config(workflow_config)
```

Keep the existing filesystem-store validation guarded by `server is None`.

- [ ] **Step 3: Run CLI test**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_cli.py::test_rpc_server_cli_config_with_mcp_source_uses_mcp_builder -q
```

Expected: pass.

## Task 5: End-to-End RPC Composition Test

**Files:**
- Modify: `tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py`

- [ ] **Step 1: Add direct neutral config server test**

Append:

```python
from wf_config import WorkflowConfigFile
from wf_mcp.broker.server import build_workflow_server_from_workflow_config


async def test_mcp_backed_rpc_can_be_built_from_neutral_workflow_config(
    tmp_path,
) -> None:
    workflow_config = WorkflowConfigFile.model_validate(
        {
            "version": 1,
            "server": {
                "store": {"kind": "filesystem", "root": str(tmp_path / "store")},
                "sources": [
                    {
                        "kind": "mcp",
                        "id": "demo.default",
                        "provider": "demo",
                        "account": "default",
                        "transport": {"kind": "stdio", "command": "demo-server"},
                    }
                ],
            },
        }
    )
    server = build_workflow_server_from_workflow_config(workflow_config)
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as http_client:
        connections = await _rpc(
            http_client, "workflow.admin.connections.list", {}
        )

    assert connections["result"]["connections"][0]["id"] == "demo.default"
```

- [ ] **Step 2: Run test**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py::test_mcp_backed_rpc_can_be_built_from_neutral_workflow_config -q
```

Expected: pass.

## Task 6: Document Completion and Legacy Status

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`
- Modify: `docs/wf_cli.md`

- [ ] **Step 1: Update roadmap**

In `docs/current_roadmap.md`, under the wider config bullet, append:

```markdown
    Runtime bridge complete: neutral `kind: "mcp"` source entries can now build
    the MCP-backed `WorkflowServer`. `--mcp-config` remains supported as a
    legacy compatibility path while new configs should prefer
    `server.sources[]`.
```

- [ ] **Step 2: Update long-lived API spec**

In the Slice 1/2 status area, append:

```markdown
   Runtime bridge complete when `wf-rpc-server --config <path>` can compose an
   MCP-backed server from neutral `server.sources[]` entries. `--mcp-config`
   remains a compatibility alias until existing users migrate.
```

- [ ] **Step 3: Update CLI docs**

In `docs/wf_cli.md`, under "Remote Server", add a neutral config example:

```markdown
Prefer neutral workflow config for new MCP-backed servers:

```json
{
  "version": 1,
  "server": {
    "store": {"kind": "filesystem", "root": ".wf_store"},
    "transports": [{"kind": "rpc_http", "host": "127.0.0.1", "port": 8765}],
    "sources": [
      {
        "kind": "mcp",
        "id": "everything.default",
        "provider": "everything",
        "account": "default",
        "transport": {"kind": "stdio", "command": "uvx", "args": ["mcp-server-everything"]}
      }
    ]
  }
}
```

`--mcp-config` is still accepted for legacy broker config files.
```

- [ ] **Step 4: Run docs diff**

Run:

```bash
git diff -- docs/current_roadmap.md docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md docs/wf_cli.md
```

Expected: docs describe neutral config as preferred and `--mcp-config` as legacy.

## Task 7: Final Verification and Commit

**Files:**
- All touched files from prior tasks.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_workflow_config_bridge.py tests/wf_transport_rpc_http/test_cli.py tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py -q
```

Expected: pass. If the existing import-direction guard still fails in unrelated runs, mention it in the report; this slice reduces but may not fully remove the current `wf_transport_rpc_http.cli -> wf_mcp` dependency.

- [ ] **Step 2: Run lint/type checks**

Run:

```bash
uv run ruff check src/wf_mcp src/wf_transport_rpc_http tests/wf_mcp tests/wf_transport_rpc_http
uv run basedpyright --level error src/wf_mcp src/wf_transport_rpc_http tests/wf_mcp tests/wf_transport_rpc_http
```

Expected: both pass with 0 errors.

- [ ] **Step 3: Commit**

Run:

```bash
git add src/wf_mcp src/wf_transport_rpc_http tests/wf_mcp tests/wf_transport_rpc_http docs/current_roadmap.md docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md docs/wf_cli.md
git commit -m "feat: build mcp server from workflow config"
```

## Self-Review Checklist

- This plan does not move MCP runtime/session logic into `wf_config`.
- Neutral config is the preferred new user-facing shape.
- Legacy `--mcp-config` remains supported.
- `server.sources[]` is the source of truth for new MCP-backed server config.
- The JSON-RPC method/app/client modules stay transport-only; only launcher/composition code touches MCP.
