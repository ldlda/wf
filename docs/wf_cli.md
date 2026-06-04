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

## Remote Server

Start a local/static JSON-RPC workflow server:

```bash
wf-rpc-server --store-root .wf_store --host 127.0.0.1 --port 8765
```

Start a JSON-RPC server backed by MCP broker config and MCP-capable sources:

```bash
wf-rpc-server --mcp-config wf_mcp.config.json --host 127.0.0.1 --port 8765
```

Then point `wf` at it:

```bash
wf --url http://127.0.0.1:8765/rpc cap list
wf --url http://127.0.0.1:8765/rpc admin registry list
```

`--mcp-config` owns the server's workflow stores, MCP connections, and source
registry. `--store-root` is for the local/static server path and cannot be
combined with `--mcp-config`.

`admin registry` shows desired persisted source entries. It is separate from
workflow artifacts and deployments, so it can be empty even when the server has
runtime sources and saved workflows.

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

`--source` filters by the exact source id shown by `wf source list`. For
example, `echo` is usually an MCP tool such as `everything.default.echo`, not a
`wf.std` builtin.

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
