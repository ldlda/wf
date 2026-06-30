# wf CLI

`wf` is the workflow platform command-line interface. It is a second front door
beside MCP: useful for shell-driven authoring, local validation, file-based
patches, and agent workflows that do better with commands than giant MCP
schemas.

`wf` uses the same config/store stack as the workflow server:

```bash
wf --config wf.config.json <command>
```

If `--config` is omitted, `wf.config.json` in the current working directory is
used. Legacy `wf_mcp.config.json` files are still supported when passed
explicitly with `--config`.

`--local` still uses the selected `--config` file. For neutral workflow configs,
it builds the configured server in the CLI process, including configured Python
sources and other source providers. Local means "same-process workflow server",
not "local-only source transports": configured MCP HTTP/stdio sources may still
open external transports from inside the CLI process. The configured durable
store is reused, but a running server's in-memory source sessions/runtime pools
are not reused. Use `--url` when you want to force the CLI to talk to an
already-running `wf-rpc-server`; `--local` and `--url` are mutually exclusive.

## Remote Server

Start a local/static JSON-RPC workflow server:

```bash
wf-rpc-server --store-root .wf_store --host 127.0.0.1 --port 8765
```

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
Convert a legacy broker config into the neutral config shape:

```bash
wf config migrate-mcp wf_mcp.config.json --output wf.json
```

Validate a neutral workflow config before starting a server:

```bash
wf config validate wf.json
```

`validate` checks JSON/model shape, resolves config-relative paths, and imports
trusted static Python sources so missing modules or registries fail before
server startup. MCP sources are shape-validated only; use `wf status`,
`wf source list`, or `wf deploy validate --live` against a running server for
live upstream checks.

For a complete Python-source flow from `ops.py` through deployment/run, see the
[`Python source runbook`](runbooks/python-source.md).

The old `store_root` field maps to
`server.store: {"kind": "filesystem", "root": ...}`; old `connections[]` map to
`server.sources[]` entries with `kind: "mcp"`.

`server.store` is currently the default root for all file-backed server state:
workflow artifacts/deployments/runs, source registry entries, catalog cache, and
local/dev auth records. Role-specific store overrides are now supported via
`server.stores.*` (e.g. `server.stores.workflow`, `server.stores.auth`,
`server.stores.source_registry`, `server.stores.catalog_cache`); missing roles
continue to fall back to `server.store`. For filesystem configs, role-specific
store overrides can split local/dev auth records and catalog cache from workflow
records.

Start a JSON-RPC server backed by MCP broker config and MCP-capable sources:

```bash
wf-rpc-server --mcp-config wf_mcp.config.json --host 127.0.0.1 --port 8765
```

Then point `wf` at it:

```bash
wf --url http://127.0.0.1:8765/rpc cap list
wf --url http://127.0.0.1:8765/rpc admin registry list
```

For a bounded end-to-end product check, use the
[`RPC CLI smoke runbook`](runbooks/rpc-cli-smoke.md). It keeps list/trace output
small and avoids dumping arbitrary MCP resource payloads.

`--mcp-config` owns the server's workflow stores, MCP connections, and source
registry. `--store-root` is for the local/static server path and cannot be
combined with `--mcp-config`.

`admin registry` shows desired persisted source entries. It is separate from
workflow artifacts and deployments, so it can be empty even when the server has
runtime sources and saved workflows.

After `wf admin registry add/update/enable/disable/remove`, call:

```bash
wf --url http://127.0.0.1:8765/rpc admin registry apply
```

Apply updates the running server's source graph from desired registry state.
It is explicit in v1; registry mutations are not auto-applied.

Check the selected target:

```bash
wf status
wf --url http://127.0.0.1:8765/rpc status
```

`status` is read-only. It reports the selected target, capability/source
availability, durable run counts/latest run, admin counts, auth record count,
and desired registry count when the target exposes those surfaces. It does not
return auth payload values, trace entries, or checkpoint state.

Schema discovery:

```bash
wf schema
wf schema draft
wf schema raw --verbose
wf schema raw --full
```

`--full` is an alias for `--verbose`; docs use `--verbose` as the canonical
flag.

### Diagnose A Source

Use `wf source diagnose <source_id>` to inspect source health before calling
capabilities:

```bash
wf --config wf.config.json source diagnose gdrive.personal
```

The output reports transport kind, auth reference, whether the auth record
exists, whether the auth scheme is compatible with the transport, catalog
snapshot counts, and non-secret diagnostics. Secret payload values are never
printed.

List resource and prompt names exposed by a source:

```bash
wf --config wf.config.json source resources everything.default
wf --config wf.config.json source prompts everything.default --format json
```

These commands read source inventory only. They do not fetch resource content or
render prompts, which can be large or stateful upstream operations.

## Output Policy

JSON is the default for detail, mutation, and execution commands unless a
command documents a safer human default. Some inventory commands default to
line-oriented names/ids to avoid dumping large payloads.

List/discovery commands may support:

```text
--format json      # complete machine-readable payload
--format ids       # one identifier per line
--format compact   # one concise line per item
```

Detail and mutation commands are JSON-only unless documented otherwise.

There is no `table` format in v1.

By default, expected operation failures are shown as compact CLI errors without
Python tracebacks. Use the root `--verbose` flag when debugging internal
failures:

```bash
wf --verbose --url http://127.0.0.1:8765/rpc source inspect missing.source
```

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

Call one capability once before creating a draft:

```bash
wf cap call wf.std.constant --input '{"value": "hello"}'
wf --url http://127.0.0.1:8765/rpc cap call everything.default.echo --input '{"message": "hello"}'
```

Use `--format compact` for a bounded one-line summary that avoids dumping large
MCP content-block envelopes:

```bash
wf cap call wf.std.constant --input '{"value": "hello"}' --format compact
```

Use `--unwrap-text` to extract exactly one MCP text content block. This implies
text output and refuses images, resources, blobs, multiple content blocks, and
non-MCP output:

```bash
wf cap call everything.default.echo --input '{"message": "hello"}' --unwrap-text
```

Use `--max-output-chars N` to bound compact/text terminal output. JSON output
is never truncated.

`cap call` is an authoring/runtime smoke test. It uses the same local or remote
target selection as the rest of the CLI and returns a normalized outcome,
output, source id, and diagnostics. Use it to confirm payload shape and upstream
source reachability before spending time on a draft workspace.

Be careful with raw MCP capabilities: some tools/resources can return large
content-block envelopes, including base64 payloads. Prefer known-small smoke
capabilities such as `wf.std.constant` unless you explicitly need to test a
specific upstream source.

## Draft Workspaces

Create a draft from a capability:

```bash
wf draft create concat_ws --capability wf.std.concat --name concat_ws
```

Capability-backed draft creation auto-binds required capability inputs only.
Optional inputs are not wired by default. Bind one when the workflow should
expose it; the focused helper projects the workflow input schema:

```bash
wf draft bind report_ws --revision 2 --step call --from input.path --to local.path
```

Use `wf draft set-input --merge` instead when adding several explicit mappings
for fields already declared in the workflow input or state schema.
to an existing step input map.

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

For larger structural edits, prefer a patch file:

```bash
wf draft patch concat_ws \
  --revision 1 \
  --input-file draft-patch.json
```

Focused draft edit commands cover common graph edits without writing RFC 6902
patches directly:

```bash
wf draft set-name concat_ws --revision 1 --name concat_ws_v2
wf draft set-route concat_ws --revision 2 --step call --outcome ok --to __end__
wf draft set-input concat_ws --revision 3 --step call --map input.items=items --map input.separator=separator
wf draft set-output concat_ws --revision 4 --step call --map value=state.value
wf draft set-workflow-output concat_ws --revision 5 --map state.value=result
wf draft set-input concat_ws --revision 6 --step call --merge --map input.limit=limit
wf draft branch concat_ws --revision 7 --step call --route ok=__end__ --route error=tool_error
wf draft handle concat_ws --revision 8 --to fail --branch lookup:error --branch transform:error
wf draft compile concat_ws
```

`set-input` maps graph source paths to node-local input fields:
`input.text=text` means `input.text -> local.text`. Targets are bare
node-local field names: write `--map input.text=text`, not
`--map input.text=local.text`.

`set-output` maps node-local output fields to workflow state paths:
`text=state.text` means `local.text -> state.text`.

`set-workflow-output` maps graph source paths (`input.*`, `state.*`, or
`context.*`) to top-level output fields: `state.value=result` means
`state.value -> output.result`.

For single-field `input.*` and `state.*` sources, the command projects missing
top-level `output_schema` fields from the source schema. More complex or
undeclared paths still rely on `wf draft validate` diagnostics.

By default, `set-input`, `set-output`, and `set-workflow-output` replace the
whole map for that step or output scope. Use repeated `--map` flags in one
command when you know the complete map. Use `--merge` when adding or updating
one entry across a later revision while preserving existing bindings.

### Bind A Step Path

Use `bind` when a capability step input/output binding also needs workflow
schema projection. The selected step must be capability-backed (`use: ...`)
because the command derives the schema from that capability. Direction matters:
use `input.*` or `state.*` to `local.*` for step inputs, and `local.*` to
`state.*` or `output.*` for step outputs.

```bash
wf draft bind concat_ws --revision 9 --step call --from local.value --to state.value
wf draft bind concat_ws --revision 9 --step call --from input.text --to local.text
wf draft bind concat_ws --revision 9 --step call --from local.result --to output.result
wf draft validate concat_ws
```

If the workflow schema field already exists, `bind` reuses it and only updates
the step binding. Use `set-input --merge` for pure input-map edits when no
schema projection is needed.

When validation gives a `repair_hint` with an exact focused `wf draft bind`
command, run it before falling back to JSON Patch.

Repair-hint examples:

```bash
# Declare an undeclared workflow input field and bind it to a step input
wf draft bind report_ws --revision 4 --step read --from input.path --to local.path
# Request a public workflow output; bind lowers it through state internally
wf draft bind report_ws --revision 5 --step render --from local.markdown --to output.markdown
# Set workflow output independently (no schema projection)
wf draft set-workflow-output report_ws --revision 6 --map state.markdown=markdown
```

The command combines two common edits:

- It copies the selected capability local field schema into the workflow input,
  state, or output schema at the graph path.
- It merges the matching step input or output binding.

Use `set-route` separately for outcome routing.

### Add A Capability Step To A Draft

Use `wf draft add-step` when adding a new capability-backed step
to an existing draft. The command is explicit: it does not guess missing maps.
Explicit top-level `--input input.x=x` and `--input state.x=x` mappings project
the corresponding workflow input/state schema fields from the capability input
schema.
When the capability declares multiple outcomes, provide exactly one
`--route OUTCOME=TARGET` for each declared outcome. Missing or unknown outcomes
are rejected before the draft is mutated. When `add-step --route` rejects an
outcome, use the declared outcomes and repair text from the error. Remove
unknown route entries and add one route for each missing declared outcome.

```bash
wf draft add-step report_ws \
  --revision 3 \
  --step render \
  --capability local.report.render_markdown_report \
  --from-step extract \
  --from-outcome ok \
  --route ok=__end__ \
  --route error=tool_error \
  --input state.title=title \
  --input state.summary=summary \
  --bind-output markdown=state.markdown \
  --bind-output title=state.title
```

Repeat `--input` and `--bind-output` once per mapping. Do not put multiple
mappings after a single flag; `--bind-output title=state.title
summary=state.summary` is parsed as an unexpected extra argument.

Run `wf draft validate report_ws` after adding the step. If validation returns
a `repair_hint`, prefer the focused helper in that hint before JSON Patch.

Draft commands may return `status: invalid` after persisting an edit. That is
normal for intermediate authoring. Repair diagnostics, run `wf draft validate`,
then save/compile only after the workspace is valid.

### Branch And Handle Existing Steps

Use `wf draft branch` to update routes for an existing step in one revision:

```bash
wf draft branch concat_ws --revision 6 --step call --route ok=__end__ --route error=tool_error
```

Use `wf draft handle` to route multiple source step outcomes to a common target:

```bash
wf draft handle concat_ws --revision 7 --to fail --branch lookup:error --branch transform:error
```

### Remove Draft Elements

Use remove commands to back out one bad route, step, or binding without writing
JSON Patch:

```bash
wf draft remove-route report_ws --revision 8 --step extract --outcome ok
wf draft remove-step report_ws --revision 9 --step render
wf draft remove-binding report_ws --revision 10 --step render --input title
wf draft remove-binding report_ws --revision 11 --step render --output markdown
```

Removal may leave the workspace `status: invalid`. That is normal for
intermediate authoring. Run `wf draft validate`, then repair routes or bindings
before saving or compiling.

### Compile A Draft Workspace

Use `wf draft compile` to print the compiled raw plan without mutating or saving
the draft:

```bash
wf draft compile concat_ws
```

On success, stdout is the raw plan JSON itself, not a `compiled_plan` envelope.
The API/RPC/MCP operation also returns required capability metadata. On invalid
draft status, the CLI prints the structured diagnostic envelope to stderr and
exits nonzero.

Validate:

```bash
wf draft validate concat_ws
```

Draft validation diagnostics may include `repair_hint` commands. Treat these as
the next focused command to try, not as proof that the draft is fixed. Re-run
`wf draft validate <workspace_id>` after applying a hint.

Delete a draft workspace:

```bash
wf draft delete concat_ws --confirm
```

Draft deletion removes only the draft workspace. It does not delete artifacts,
deployments, or runs.

Save as an artifact:

```bash
wf draft save concat_ws \
  --artifact concat_ws \
  --version 1 \
  --title "Concat Workflow" \
  --outcome ok
```

Use `--kind wrapper` when saving a callable wrapper artifact:

```bash
wf draft save concat_ws \
  --artifact concat_wrapper \
  --version 1 \
  --title "Concat Wrapper" \
  --kind wrapper \
  --outcome ok
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

Create an artifact directly from a raw JSON/YAML workflow plan file:

```bash
wf artifact create-from-plan workflow.plan.json \
  --artifact concat_ws \
  --version 1 \
  --title "Concat Workflow" \
  --outcome ok \
  --binding local.ops=local.ops
```

`artifact create-from-plan` expects the raw workflow plan shape (`nodes`,
`edges`, `node`). It does not accept draft workspace shape (`steps`, `routes`,
`use`).

Prefer draft workspaces for iterative authoring. Use `create-from-plan` when a
compiler, fixture, or advanced client already has a complete raw workflow plan.
Artifact save responses include `required_logical_sources` and may include
`suggested_bindings`. Copy suggested bindings into `wf deploy save --binding`
when they are present; otherwise choose the concrete source/account explicitly.

Delete an unreferenced artifact version:

```bash
wf artifact delete smoke_artifact_20260609 1 --confirm
```

The command refuses to delete artifact versions still referenced by deployments.
Delete referencing deployments first with `wf deploy delete <deployment_id>`.

## Deployments

Save a deployment from flags:

```bash
wf deploy save concat_ws.default \
  --artifact concat_ws \
  --version 1
```

`wf deploy create` is accepted as an alias for `wf deploy save`; docs use
`save` as the canonical verb because deployments are mutable records.

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

List durable stopped runs:

```bash
wf run list --limit 20
wf run list --status interrupted
wf --url http://127.0.0.1:8765/rpc run list --status failed
```

`wf run list` returns compact stopped-run summaries from the target store. It
does not include trace entries or checkpoint state. Use `wf run inspect <run_id>`
for one run summary and `wf run trace <run_id> --from 0 --limit 25` for bounded
debug detail.

Inspect a run without trace detail:

```bash
wf run inspect run_123
```

Poll a run until it stops:

```bash
wf run watch run_123 --interval 1
wf run watch run_123 --trace --trace-limit 25
```

Read a bounded trace slice:

```bash
wf run trace run_123 --from 0 --limit 25
```

Trace output can be large. Always request a bounded range.

### Interrupt Resume Schemas

Interrupted runs may include `interrupt.request_schema` and
`interrupt.resume_schema` in `wf run inspect` output. The request schema
describes the payload shown to the operator. The resume schema describes the
payload accepted by `wf run resume --payload` or `--payload-file`.

Resume payload validation happens before workflow state mutation. If validation
fails, inspect the schema and retry with a payload that matches the declared
shape.

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

Draft authoring diagnostics commonly include:

- `invalid_source_path`
- `invalid_destination_path`
- `unknown_edge_destination`
- `unknown_outcome`
- `patch_invalid`
- `revision_conflict`

## Common Diagnostics

### Local/dev auth records

Auth payload values are write-only. `list`, `inspect`, `save`, and `delete`
responses show ids, schemes, metadata, and payload keys only.

```powershell
wf admin auth save drive.work --scheme bearer --payload-file drive-auth.json
wf admin auth list
wf admin auth inspect drive.work
wf admin auth delete drive.work --confirm
```

Use source `auth_ref` values to point sources at these records. Do not commit
payload files containing real secrets.

### Source Provider Setup

For MCP HTTP, MCP stdio, Python source, `auth_ref`, and OAuth setup examples,
see the [`Source Provider Guide`](source_provider_guide.md).

Google Drive MCP is documented there as manual smoke coverage only; do not use
it as a regression fixture.

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
- `wf` does not replace MCP resources/prompts or interactive MCP clients.
