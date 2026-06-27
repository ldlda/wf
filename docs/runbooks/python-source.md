# Python Source Runbook

This runbook shows how to expose project-local Python `NodeSpec` functions as
workflow capabilities through `wf-rpc-server`.

Python sources are trusted in-process code. Importing the configured module can
run top-level module code during `wf config validate` and server startup. Keep
module top-level work small and side-effect free; put real work inside `@node`
functions.

Prefer package-style source modules and package-relative imports. For example,
use `module: "my_source.ops"` with `from .helpers import ...` inside
`my_source/ops.py`. Bare local imports such as `import helpers` use Python's
global import cache and are only best-effort when multiple configured sources
reuse the same helper/module names.

## 1. Write `ops.py`

Create a module that exports one or more `NodeSpec` objects. The simplest path
is to decorate typed functions with `wf_authoring.node` and put them in a
`registry` list.

```python
from __future__ import annotations

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

The registry can also be a mapping or a callable returning a sequence/mapping.
Every exported value must be a `NodeSpec`.

## 2. Configure The Source

Add a `kind: "python"` entry under `server.sources[]`:

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

`path` is resolved relative to the config file and added to `sys.path` before
import. This makes the module discoverable whether you run through
`uv run python` or an installed entrypoint.

The source id prefixes local names. A node named `echo` becomes
`local.ops.echo`. If a node uses the authoring namespace, such as
`authoring.echo`, that authoring prefix is replaced by the source id, producing
`local.ops.echo`.

## 3. Validate And Start

Preflight the config:

```powershell
uv run wf config validate wf.python.config.json
```

Then start the server:

```powershell
uv run wf-rpc-server --config wf.python.config.json
```

If the config includes `client.target`, the CLI can use the config directly:

```powershell
uv run wf --config wf.python.config.json status
```

You can also pass the URL explicitly:

```powershell
uv run wf --url http://127.0.0.1:8766/rpc source list
```

## 4. Call A Capability

List and call the Python capability:

```powershell
uv run wf --url http://127.0.0.1:8766/rpc cap list --source local.ops
uv run wf --url http://127.0.0.1:8766/rpc cap call local.ops.echo --input '{"text":"hello"}'
```

Expected output includes:

```json
{
  "outcome": "ok",
  "output": {"echoed": "hello"}
}
```

## 5. Save And Run A Workflow

Create a draft from the Python capability:

```powershell
uv run wf --url http://127.0.0.1:8766/rpc draft create `
  python_echo_ws --capability local.ops.echo --name python_echo
```

Save it as an artifact. Bind the configured Python source. Built-in platform
sources such as `wf.std` can be used by generated scaffolds without self-binding.

```powershell
uv run wf --url http://127.0.0.1:8766/rpc draft save python_echo_ws `
  --artifact python_echo `
  --version 1 `
  --title "Python Echo" `
  --outcome ok `
  --binding local.ops=local.ops
```

Save a deployment with the same bindings:

```powershell
uv run wf --url http://127.0.0.1:8766/rpc deploy save python_echo.default `
  --artifact python_echo `
  --version 1 `
  --binding local.ops=local.ops
```

Run it:

```powershell
uv run wf --url http://127.0.0.1:8766/rpc run start python_echo.default `
  --input '{"text":"hello workflow"}'
```

Expected output includes:

```json
{
  "outcome": "ok",
  "output": {"echoed": "hello workflow"}
}
```

## Current Limits

- Python sources are static at server startup; there is no hot reload yet.
- Python sources are trusted in-process code; there is no sandbox.
- Source registry mutation/apply support for Python sources is deferred.
- Reducer exports are deferred until a real source needs them.
