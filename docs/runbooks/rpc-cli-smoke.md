# RPC CLI Smoke Runbook

Use this runbook to verify the product path:

```text
wf CLI -> wf_transport_rpc_http -> wf_server -> wf_api -> wf_core / stores / sources
```

For an automated version of this runbook:

```bash
uv run python examples/rpc_cli_smoke.py
```

Use `--keep-temp` to preserve the generated config/store after failure.

This is a bounded smoke test, not a load test. Keep outputs compact and avoid
dumping raw upstream MCP resource payloads into terminal logs or agent context.
Some MCP servers can return huge base64 image/resource blocks.

## Prerequisites

Start the server in another terminal:

```bash
uv run wf-rpc-server --config wf.config.json --host 127.0.0.1 --port 8765
```

This runbook assumes `wf.config.json` has:

```json
{
  "client": {
    "target": {
      "kind": "rpc_http",
      "url": "http://127.0.0.1:8765/rpc"
    }
  }
}
```

You can also keep local config unchanged and pass
`--url http://127.0.0.1:8765/rpc` on every `wf` command.

## Output Safety Rules

- Prefer `--format compact` or `--format ids` for list commands.
- Do not call arbitrary resource-heavy MCP capabilities during smoke.
- Do not inspect or print raw MCP resources unless the URI is known to be small.
- Keep trace reads bounded with `--limit`.
- If a command returns a huge `content`/`resource`/base64 field, stop and add a
  safer CLI output mode before repeating it.

## 1. Server Status

```bash
uv run wf --config wf.config.json status
```

Expected:

- `target.mode` is `remote`.
- Source/capability counts are nonzero for an MCP-backed server.
- Errors, if any, are compact CLI errors unless `--verbose` is used.

## 2. Bounded Discovery

```bash
uv run wf --config wf.config.json source list --format compact
uv run wf --config wf.config.json source resources everything.default
uv run wf --config wf.config.json source prompts everything.default --format json
uv run wf --config wf.config.json cap list --source wf.std --format ids
uv run wf --config wf.config.json cap inspect wf.std.constant
```

Expected:

- `source list` includes `wf.std`.
- `source resources` and `source prompts` return bounded inventory only; they do
  not read resource bodies or render prompt templates.
- `cap list --source wf.std --format ids` returns bounded identifiers.
- `cap inspect wf.std.constant` shows the capability contract.

## 3. Direct Capability Call

```bash
uv run wf --config wf.config.json cap call wf.std.constant --input '{"value":"smoke"}'
```

Expected:

- `outcome` is `ok`.
- Output is small and machine-readable.

Optionally, test compact output:

```bash
uv run wf --config wf.config.json cap call wf.std.constant --input '{"value":"smoke"}' --format compact
```

Expected: one bounded line with `outcome=ok`.

Avoid using arbitrary MCP tools here unless their output shape is known. MCP
content-block envelopes can be large and should not be treated like compact
workflow output.

## 4. Draft -> Artifact -> Deployment -> Run

Use unique ids so repeated runs do not collide:

```bash
uv run wf --config wf.config.json draft create smoke_ws --capability wf.std.constant --name smoke_constant --title "Smoke Constant"
uv run wf --config wf.config.json draft validate smoke_ws
uv run wf --config wf.config.json draft save smoke_ws --artifact smoke_artifact --version 1 --title "Smoke Artifact" --outcome ok
uv run wf --config wf.config.json deploy save smoke_deploy --artifact smoke_artifact --version 1
uv run wf --config wf.config.json deploy validate smoke_deploy
uv run wf --config wf.config.json run start smoke_deploy --input '{"value":"from workflow"}'
```

Expected:

- Draft validation is `valid`.
- Deployment validation is runnable.
- Run result has `outcome: "ok"`.
- Capture the returned `run_id` for the trace step.

## 5. Inspect And Bounded Trace

Replace `run_...` with the id returned by `run start`:

```bash
uv run wf --config wf.config.json run inspect run_...
uv run wf --config wf.config.json run trace run_... --from 0 --limit 10
```

Expected:

- Inspect returns the run summary and output.
- Trace returns a bounded number of frames.

## 6. Cleanup

Delete in dependency order: deployment first, then artifact, then draft.

```bash
uv run wf --config wf.config.json deploy delete smoke_deploy
uv run wf --config wf.config.json artifact delete smoke_artifact 1 --confirm
uv run wf --config wf.config.json draft delete smoke_ws --confirm
```

Expected:

- Deployment delete succeeds.
- Artifact delete returns `deleted: true`.
- Draft delete returns `deleted: true`.

If artifact delete returns `deleted: false` with `blocked_by_deployments`, delete
the listed deployments and retry.
