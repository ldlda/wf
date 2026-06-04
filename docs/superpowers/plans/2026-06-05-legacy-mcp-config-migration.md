# Legacy MCP Config Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert old `wf_mcp.config.json` files into the new neutral `WorkflowConfigFile` shape and expose a CLI migration command.

**Architecture:** The migration is compatibility-only: old MCP broker config remains readable, but new output should use `wf_config.server.store` and `wf_config.server.sources[]`. Before adding the converter, fix the neutral MCP source bridge so it produces the flat connection metadata shape still expected by `wf_mcp.sdk.adapter` and `wf_mcp.runtime.factory`.

**Tech Stack:** Pydantic v2 config models, Typer CLI, existing `wf_config` / `wf_mcp.control.models` / `wf_mcp.broker.config` modules.

---

## File Structure

- Modify `src/wf_mcp/source_registry.py`: fix `workflow_mcp_source_to_connection_config()` to emit flat runtime metadata, not nested transport dicts.
- Create or modify `tests/wf_mcp/test_workflow_config_bridge.py`: add runtime-metadata assertions.
- Modify `src/wf_mcp/broker/config.py`: add `workflow_config_from_broker_config_file()` and `migrate_broker_config_file()`.
- Modify `tests/wf_mcp/test_workflow_config_migration.py`: test legacy config file conversion.
- Modify `src/wf_cli/commands/config.py` and `src/wf_cli/app.py`: add `wf config migrate-mcp`.
- Create `tests/wf_cli/test_config_migration.py`: test CLI conversion output.
- Modify docs: `docs/wf_cli.md`, `docs/current_roadmap.md`, `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`.

## Current Context

Neutral MCP source config exists in `wf_config.models.McpSourceConfig`.

MCP runtime code currently expects `ConnectionConfig.metadata` to be flat:

```python
# src/wf_mcp/sdk/adapter.py and src/wf_mcp/runtime/factory.py
transport = connection.metadata.get("transport", "stdio")
command = connection.metadata["command"]
args = list(connection.metadata.get("args", []))
url = connection.metadata["url"]
```

The current `workflow_mcp_source_to_connection_config()` added by the previous slice stores:

```python
"transport": transport.model_dump(mode="json")
```

That is fine for registry-like payloads, but wrong for actual runtime execution. Fix that before writing the migration converter.

## Task 1: Lock Runtime Metadata Shape for Neutral MCP Sources

**Files:**
- Modify: `tests/wf_mcp/test_workflow_config_bridge.py`
- Modify: `src/wf_mcp/source_registry.py`

- [ ] **Step 1: Strengthen the stdio conversion test**

In `tests/wf_mcp/test_workflow_config_bridge.py`, update the existing stdio assertion from nested transport dict:

```python
assert connection.metadata["transport"] == {
    "kind": "stdio",
    "command": "uvx",
    "args": ["mcp-server-everything"],
    "env": {"DEBUG": "1"},
}
```

to flat runtime metadata:

```python
assert connection.metadata["transport"] == "stdio"
assert connection.metadata["command"] == "uvx"
assert connection.metadata["args"] == ["mcp-server-everything"]
assert connection.metadata["env"] == {"DEBUG": "1"}
```

- [ ] **Step 2: Add HTTP conversion test**

Append this test:

```python
def test_broker_config_from_workflow_config_converts_mcp_http_source(tmp_path) -> None:
    workflow_config = WorkflowConfigFile.model_validate(
        {
            "version": 1,
            "server": {
                "store": {"kind": "filesystem", "root": str(tmp_path / "store")},
                "sources": [
                    {
                        "kind": "mcp",
                        "id": "context7.default",
                        "provider": "context7",
                        "account": "default",
                        "transport": {
                            "kind": "http",
                            "url": "http://127.0.0.1:3000/mcp",
                            "headers": {"X-Test": "yes"},
                        },
                    }
                ],
            },
        }
    )

    broker_config = broker_config_from_workflow_config(workflow_config)

    connection = broker_config.connections[0]
    assert connection.metadata["transport"] == "streamable_http"
    assert connection.metadata["url"] == "http://127.0.0.1:3000/mcp"
    assert connection.metadata["headers"] == {"X-Test": "yes"}
```

- [ ] **Step 3: Run tests and verify failure**

Run:

```bash
uv run pytest tests/wf_mcp/test_workflow_config_bridge.py -q
```

Expected: fail because metadata is still nested under `"transport"`.

- [ ] **Step 4: Fix runtime metadata conversion**

In `src/wf_mcp/source_registry.py`, replace the metadata-building block inside `workflow_mcp_source_to_connection_config()` with:

```python
    transport = getattr(source, "transport")
    metadata = dict(getattr(source, "metadata", {}))
    if transport.kind == "stdio":
        metadata.update(
            {
                "transport": "stdio",
                "command": transport.command,
                "args": list(transport.args),
                "env": dict(transport.env),
                "source_registry": False,
            }
        )
    elif transport.kind == "http":
        metadata.update(
            {
                "transport": "streamable_http",
                "url": str(transport.url),
                "headers": dict(transport.headers),
                "source_registry": False,
            }
        )
    else:
        raise ValueError(f"unsupported wf_config MCP transport {transport.kind!r}")
```

Keep the existing `profile` and `auth_ref` handling after this block.

- [ ] **Step 5: Run tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_workflow_config_bridge.py -q
```

Expected: pass.

## Task 2: Add Legacy Config to WorkflowConfig Conversion Tests

**Files:**
- Create: `tests/wf_mcp/test_workflow_config_migration.py`

- [ ] **Step 1: Create test file**

Create `tests/wf_mcp/test_workflow_config_migration.py`:

```python
from __future__ import annotations

from pathlib import Path

from wf_mcp.broker.config import migrate_broker_config_file


def test_migrate_broker_config_file_converts_stdio_connection(tmp_path: Path) -> None:
    legacy_path = tmp_path / "wf_mcp.config.json"
    legacy_path.write_text(
        """
{
  "store_root": ".wf_mcp_store",
  "connections": [
    {
      "id": "everything.default",
      "server": "everything",
      "account": "default",
      "enabled": true,
      "source_config_ownership": "seed",
      "metadata": {
        "transport": "stdio",
        "command": "uvx",
        "args": ["mcp-server-everything"],
        "env": {"DEBUG": "1"},
        "profile": "dev",
        "auth_ref": "auth.everything.default",
        "description": "Everything test server"
      }
    }
  ]
}
""",
        encoding="utf-8",
    )

    config = migrate_broker_config_file(legacy_path)

    assert config.server.store.kind == "filesystem"
    assert config.server.store.root == ".wf_mcp_store"
    assert len(config.server.sources) == 1
    source = config.server.sources[0]
    assert source.kind == "mcp"
    assert source.id == "everything.default"
    assert source.provider == "everything"
    assert source.account == "default"
    assert source.enabled is True
    assert source.ownership == "seed"
    assert source.profile == "dev"
    assert source.auth_ref == "auth.everything.default"
    assert source.transport.kind == "stdio"
    assert source.transport.command == "uvx"
    assert source.transport.args == ("mcp-server-everything",)
    assert source.transport.env == {"DEBUG": "1"}
    assert source.metadata["description"] == "Everything test server"


def test_migrate_broker_config_file_converts_streamable_http_connection(
    tmp_path: Path,
) -> None:
    legacy_path = tmp_path / "wf_mcp.config.json"
    legacy_path.write_text(
        """
{
  "store_root": "store",
  "connections": [
    {
      "id": "context7.default",
      "server": "context7",
      "account": "default",
      "metadata": {
        "transport": "streamable-http",
        "url": "http://127.0.0.1:3000/mcp",
        "headers": {"X-Test": "yes"},
        "description": "HTTP server"
      }
    }
  ]
}
""",
        encoding="utf-8",
    )

    config = migrate_broker_config_file(legacy_path)

    source = config.server.sources[0]
    assert source.kind == "mcp"
    assert source.transport.kind == "http"
    assert str(source.transport.url) == "http://127.0.0.1:3000/mcp"
    assert source.transport.headers == {"X-Test": "yes"}
    assert source.metadata["description"] == "HTTP server"
    assert source.metadata["legacy_transport"] == "streamable-http"


def test_migrate_broker_config_file_converts_sse_connection(tmp_path: Path) -> None:
    legacy_path = tmp_path / "wf_mcp.config.json"
    legacy_path.write_text(
        """
{
  "store_root": "store",
  "connections": [
    {
      "id": "legacy.default",
      "server": "legacy",
      "account": "default",
      "metadata": {
        "transport": "sse",
        "url": "http://127.0.0.1:3000/sse"
      }
    }
  ]
}
""",
        encoding="utf-8",
    )

    config = migrate_broker_config_file(legacy_path)

    source = config.server.sources[0]
    assert source.transport.kind == "http"
    assert str(source.transport.url) == "http://127.0.0.1:3000/sse"
    assert source.metadata["legacy_transport"] == "sse"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run pytest tests/wf_mcp/test_workflow_config_migration.py -q
```

Expected: fail because `migrate_broker_config_file` does not exist.

## Task 3: Implement Legacy Config Conversion Library

**Files:**
- Modify: `src/wf_mcp/broker/config.py`

- [ ] **Step 1: Add imports**

Update imports:

```python
from wf_config import WorkflowConfigFile
from wf_config.models import FilesystemStoreConfig, McpSourceConfig
```

If `WorkflowConfigFile` is already imported, only add the model imports.

- [ ] **Step 2: Add metadata conversion helpers**

Add these helpers above `load_broker_config()`:

```python
_HTTP_TRANSPORTS = {"http", "streamable-http", "streamable_http", "sse"}


def _source_metadata_without_transport(metadata: dict[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in metadata.items()
        if key
        not in {
            "transport",
            "command",
            "args",
            "env",
            "cwd",
            "url",
            "headers",
            "profile",
            "auth_ref",
        }
    }


def _mcp_source_from_connection(connection) -> McpSourceConfig:
    metadata = dict(connection.metadata)
    transport_kind = str(metadata.get("transport", "stdio"))
    profile = metadata.get("profile")
    auth_ref = metadata.get("auth_ref")
    source_metadata = _source_metadata_without_transport(metadata)
    if transport_kind == "stdio":
        command = metadata.get("command")
        if not isinstance(command, str) or not command:
            raise ValueError(
                f"legacy stdio connection {connection.id!r} requires metadata.command"
            )
        transport = {
            "kind": "stdio",
            "command": command,
            "args": list(metadata.get("args", [])),
            "env": dict(metadata.get("env", {})),
        }
        cwd = metadata.get("cwd")
        if cwd is not None:
            source_metadata["cwd"] = cwd
    elif transport_kind in _HTTP_TRANSPORTS:
        url = metadata.get("url")
        if not isinstance(url, str) or not url:
            raise ValueError(
                f"legacy HTTP connection {connection.id!r} requires metadata.url"
            )
        transport = {
            "kind": "http",
            "url": url,
            "headers": dict(metadata.get("headers", {})),
        }
        source_metadata["legacy_transport"] = transport_kind
    else:
        raise ValueError(
            f"legacy connection {connection.id!r} uses unsupported transport "
            f"{transport_kind!r}"
        )

    return McpSourceConfig.model_validate(
        {
            "kind": "mcp",
            "id": connection.id,
            "enabled": connection.enabled,
            "provider": connection.server,
            "account": connection.account,
            "profile": profile if isinstance(profile, str) else None,
            "ownership": connection.source_config_ownership,
            "transport": transport,
            "auth_ref": auth_ref if isinstance(auth_ref, str) else None,
            "metadata": source_metadata,
        }
    )
```

- [ ] **Step 3: Add public conversion function**

Add after `load_broker_config()`:

```python
def migrate_broker_config_file(path: str | Path) -> WorkflowConfigFile:
    """Convert legacy wf_mcp.config.json into neutral workflow config.

    This does not write files. Callers choose whether to serialize the returned
    config to disk or inspect it first.
    """
    config_path = Path(path)
    data = json.loads(config_path.read_text(encoding="utf-8"))
    legacy = BrokerConfigFile.model_validate(data)
    return WorkflowConfigFile(
        server={
            "store": FilesystemStoreConfig(root=legacy.store_root),
            "sources": [
                _mcp_source_from_connection(connection)
                for connection in legacy.connections
            ],
        }
    )
```

- [ ] **Step 4: Export it**

Add `"migrate_broker_config_file"` to `__all__`.

- [ ] **Step 5: Run migration tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_workflow_config_migration.py tests/wf_mcp/test_workflow_config_bridge.py -q
```

Expected: pass.

## Task 4: Add CLI Migration Command

**Files:**
- Create: `src/wf_cli/commands/config.py`
- Modify: `src/wf_cli/app.py`
- Create: `tests/wf_cli/test_config_migration.py`

- [ ] **Step 1: Create CLI command module**

Create `src/wf_cli/commands/config.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from wf_mcp.broker.config import migrate_broker_config_file

from wf_cli.io import emit_json

app = typer.Typer(
    name="config",
    help="Inspect and migrate workflow config files.",
    no_args_is_help=True,
)


@app.command("migrate-mcp")
def migrate_mcp_config(
    input_path: Annotated[
        Path,
        typer.Argument(help="Legacy wf_mcp.config.json path."),
    ],
    output_path: Annotated[
        Path | None,
        typer.Option("--output", help="Write neutral workflow config JSON here."),
    ] = None,
) -> None:
    """Convert legacy MCP broker config into neutral workflow config."""
    config = migrate_broker_config_file(input_path)
    payload = config.model_dump(mode="json")
    if output_path is None:
        emit_json(payload)
        return
    output_path.write_text(
        config.model_dump_json(indent=2),
        encoding="utf-8",
    )
    emit_json({"status": "written", "path": str(output_path)})
```

- [ ] **Step 2: Register command in app**

In `src/wf_cli/app.py`, add `config` to the command import tuple:

```python
from .commands import (
    admin,
    artifacts,
    caps,
    config,
    deployments,
    docs,
    drafts,
    explain,
    runs,
    schema,
    sources,
)
```

Add:

```python
app.add_typer(config.app, name="config")
```

Place it near `schema`/`docs`.

- [ ] **Step 3: Add CLI tests**

Create `tests/wf_cli/test_config_migration.py`:

```python
from __future__ import annotations

import json

from typer.testing import CliRunner

from wf_cli.app import app


def test_wf_config_migrate_mcp_prints_neutral_config(tmp_path) -> None:
    legacy_path = tmp_path / "wf_mcp.config.json"
    legacy_path.write_text(
        """
{
  "store_root": ".wf_mcp_store",
  "connections": [
    {
      "id": "everything.default",
      "server": "everything",
      "account": "default",
      "metadata": {
        "transport": "stdio",
        "command": "uvx",
        "args": ["mcp-server-everything"]
      }
    }
  ]
}
""",
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["config", "migrate-mcp", str(legacy_path)])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["server"]["store"] == {
        "kind": "filesystem",
        "root": ".wf_mcp_store",
    }
    source = payload["server"]["sources"][0]
    assert source["kind"] == "mcp"
    assert source["id"] == "everything.default"
    assert source["transport"]["kind"] == "stdio"
    assert source["transport"]["command"] == "uvx"


def test_wf_config_migrate_mcp_writes_output_file(tmp_path) -> None:
    legacy_path = tmp_path / "wf_mcp.config.json"
    output_path = tmp_path / "wf.json"
    legacy_path.write_text(
        """
{
  "store_root": "store",
  "connections": [
    {
      "id": "context7.default",
      "server": "context7",
      "account": "default",
      "metadata": {
        "transport": "streamable_http",
        "url": "http://127.0.0.1:3000/mcp"
      }
    }
  ]
}
""",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        ["config", "migrate-mcp", str(legacy_path), "--output", str(output_path)],
    )

    assert result.exit_code == 0, result.output
    status = json.loads(result.output)
    assert status["status"] == "written"
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["server"]["sources"][0]["transport"]["kind"] == "http"
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
uv run pytest tests/wf_cli/test_config_migration.py -q
```

Expected: pass.

## Task 5: Update Docs and Mark Slice Complete

**Files:**
- Modify: `docs/wf_cli.md`
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`

- [ ] **Step 1: Update CLI docs**

In `docs/wf_cli.md`, replace the future migration note:

```markdown
Future migration support should let users convert that legacy shape into the
neutral config above. The old `store_root` field maps to
`server.store: {"kind": "filesystem", "root": ...}`; old `connections[]` map to
`server.sources[]` entries with `kind: "mcp"`.
```

with:

```markdown
Convert a legacy broker config into the neutral config shape:

```bash
wf config migrate-mcp wf_mcp.config.json --output wf.json
```

The old `store_root` field maps to
`server.store: {"kind": "filesystem", "root": ...}`; old `connections[]` map to
`server.sources[]` entries with `kind: "mcp"`.
```

- [ ] **Step 2: Update roadmap**

In `docs/current_roadmap.md`, under "Legacy config migration", append:

```markdown
    Completed: `wf config migrate-mcp` converts legacy broker config files into
    neutral workflow config files without mutating the original.
```

- [ ] **Step 3: Update long-lived API spec**

In `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`, under "Legacy MCP config migration", append:

```markdown
   Completed when `wf config migrate-mcp <legacy> --output <workflow-config>`
   writes a neutral config that can be used by `wf-rpc-server --config`.
```

## Task 6: Final Verification and Commit

**Files:**
- All touched files from prior tasks.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_workflow_config_bridge.py tests/wf_mcp/test_workflow_config_migration.py tests/wf_cli/test_config_migration.py tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py -q
```

Expected: pass.

- [ ] **Step 2: Run lint/type checks**

Run:

```bash
uv run ruff check src/wf_mcp src/wf_cli tests/wf_mcp tests/wf_cli
uv run basedpyright --level error src/wf_mcp src/wf_cli tests/wf_mcp tests/wf_cli
```

Expected: pass with 0 errors.

- [ ] **Step 3: Commit**

Run:

```bash
git add src/wf_mcp src/wf_cli tests/wf_mcp tests/wf_cli docs/wf_cli.md docs/current_roadmap.md docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md
git commit -m "feat: migrate legacy mcp config"
```

## Self-Review Checklist

- Converter does not mutate the legacy input file.
- `server.store` remains the only store destination; no parallel `store_root` is added to neutral config.
- `stdio` conversion preserves command/args/env.
- `http`, `streamable-http`, `streamable_http`, and `sse` legacy transports normalize to neutral HTTP source transport.
- `sse` remains supported only as migration compatibility metadata.
- Runtime connection metadata is flat so MCP SDK/runtime adapters still work.
