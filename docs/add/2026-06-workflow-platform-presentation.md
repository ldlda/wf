# Workflow Platform Presentation

Date: 2026-06-12

This is a compact presentation narrative for the current product shape. It is
not a full architecture reference; use the linked docs for implementation
detail.

## One-Sentence Thesis

LLMs should plan typed workflows, while a deterministic runtime executes those
workflows against explicit, validated capability sources.

## The Problem

Agents are good at deciding what should happen next, but bad at being the thing
that directly owns side effects, retries, durable state, and schema contracts.

The platform separates those jobs:

- The LLM or human author chooses and edits workflow structure.
- The workflow runtime executes a typed graph.
- Source providers expose callable capabilities.
- Stores persist artifacts, deployments, and stopped runs.
- Transports let CLI, future UI, and other clients talk to the same server.

## Current Product Path

```text
wf CLI
  -> JSON-RPC transport
  -> WorkflowServer
  -> WorkflowApi
  -> wf_core runtime + wf_artifacts stores + wf_sources_* providers
```

The preferred server entrypoint is:

```powershell
uv run wf-rpc-server --config wf.config.json
```

The preferred client entrypoint is:

```powershell
uv run wf --config wf.config.json status
```

`wf-mcp` still exists for legacy/special-purpose MCP-facing work, but the
durable product path is now `wf-rpc-server` plus `wf`.

## Core Model

A workflow is a typed graph:

- `input_schema` validates run input.
- `state_schema` defines workflow memory and reducer behavior.
- `output_schema` defines the final result contract.
- nodes do real work through `NodeSpec` handlers.
- edges route by declared outcomes.
- deployments bind logical source requirements to concrete sources.

The runtime does not know whether a node came from MCP, Python, OpenAPI, or a
built-in package. It resolves a `NodeSpec`, validates payloads, executes, records
trace, and commits reducer-aware state changes.

## Source Model

The common provider output is `CapabilitySource`.

```text
source provider
  -> CapabilitySource
  -> WorkflowSpecProvider
  -> WorkflowApi
```

Current source families:

| Source | Kind | Role |
| --- | --- | --- |
| `wf.std` | `system` | built-in standard workflow nodes and reducers |
| `wf.recipes` | `system` | first-party workflow recipes |
| MCP sources | `connection` | upstream MCP tools/resources/prompts via persistent sessions |
| Python sources | `python` | trusted project-local `NodeSpec` registries |

The first explicit provider seam is intentionally small:

```python
class WorkflowSourceProvider(Protocol):
    def load_sources(self) -> Mapping[str, CapabilitySource]: ...
```

This seam is for static source inventory. MCP also has runtime pools,
auth/catalog stores, admin/apply behavior, and live checks, so it should not be
forced into a tiny static interface too early.

## Demo: Python Source End To End

Write `ops.py`:

```python
from pydantic import BaseModel
from wf_authoring import node


class EchoInput(BaseModel):
    text: str


class EchoOutput(BaseModel):
    echoed: str


@node(name="echo")
def echo(payload: EchoInput) -> EchoOutput:
    return EchoOutput(echoed=payload.text)


registry = [echo]
```

Configure it:

```json
{
  "version": 1,
  "client": {
    "target": {
      "kind": "rpc_http",
      "url": "http://127.0.0.1:8766/rpc",
      "timeout_seconds": 30
    }
  },
  "server": {
    "store": {"kind": "filesystem", "root": ".wf_python_store"},
    "transports": [
      {"kind": "rpc_http", "host": "127.0.0.1", "port": 8766, "path": "/rpc"}
    ],
    "sources": [
      {
        "kind": "python",
        "id": "local.ops",
        "path": ".",
        "module": "ops",
        "registry": "registry"
      }
    ]
  }
}
```

Validate before starting:

```powershell
uv run wf config validate wf.python.config.json
```

Start the server:

```powershell
uv run wf-rpc-server --config wf.python.config.json
```

Call the capability:

```powershell
uv run wf --config wf.python.config.json cap call local.ops.echo --input '{"text":"hello"}'
```

Turn it into a saved workflow:

```powershell
uv run wf --config wf.python.config.json draft create-from-capability `
  python_echo_ws local.ops.echo --name python_echo

uv run wf --config wf.python.config.json draft save python_echo_ws `
  --artifact python_echo `
  --version 1 `
  --title "Python Echo" `
  --outcome ok `
  --binding local.ops=local.ops

uv run wf --config wf.python.config.json deploy save python_echo.default `
  --artifact python_echo `
  --version 1 `
  --binding local.ops=local.ops

uv run wf --config wf.python.config.json run start python_echo.default `
  --input '{"text":"hello workflow"}'
```

Expected run result:

```json
{
  "status": "completed",
  "outcome": "ok",
  "output": {"echoed": "hello workflow"}
}
```

## What Works Today

- CLI can target local or remote workflow servers.
- JSON-RPC server can run from neutral config.
- `wf config validate` checks config shape, config-relative paths, and trusted
  Python source imports.
- `wf status` summarizes target, sources, capabilities, runs, admin surfaces,
  and registry availability.
- Capabilities can be listed, inspected, and called directly.
- Drafts can be created from capabilities and saved as immutable artifacts.
- Deployments bind logical sources to concrete sources.
- Runs are persisted at stopped boundaries and can be inspected/listed.
- MCP upstream sessions are stateful through `McpRuntimePool`.
- Python sources can run through the full draft -> artifact -> deployment -> run
  lifecycle.

## Honest Limits

- Python sources are trusted in-process code; there is no sandbox.
- Python sources are static at server startup; no hot reload yet.
- Python source registry/apply support is not implemented yet.
- `WorkflowSourceProvider` covers static inventory only, not runtime/admin/apply
  lifecycle.
- Run deletion is not implemented.
- File-backed stores are the proven storage backend; SQL/secret-manager stores
  are future work.
- MCP app/widget passthrough is not a durable workflow product feature yet.

## Next Direction

Near-term work should make source providers more regular without prematurely
flattening them:

- provider lifecycle for add/update/remove/apply/reload across source families
- OpenAPI source provider using the same `CapabilitySource` shape
- clearer config/status diagnostics for source health
- optional Python source development reload
- production-grade auth/secret store integration

## Reading Map

- [`docs/wf_cli.md`](../wf_cli.md): CLI command reference.
- [`docs/runbooks/python-source.md`](../runbooks/python-source.md): Python
  source runbook.
- [`docs/source_architecture.md`](../source_architecture.md): source provider
  package map.
- [`docs/project_map.md`](../project_map.md): package and entrypoint map.
- [`docs/current_roadmap.md`](../current_roadmap.md): active roadmap.
