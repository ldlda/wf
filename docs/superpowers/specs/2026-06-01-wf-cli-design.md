# wf CLI Design

## Purpose

`wf` is a platform CLI for authoring, validating, deploying, and running
workflow artifacts without forcing every operation through MCP request/response
schemas.

The CLI is an agent-facing and human-facing front door. It should make the
workflow lifecycle easy to drive from shell commands, files, diffs, and local
validation. MCP remains useful for interactive discovery/control inside MCP
clients, but CLI should become the better surface for large authoring loops.

## Core Decision

Create a new package:

```text
src/wf_cli/
```

Do not place the CLI under `wf_mcp`.

Reason: workflow authoring and run lifecycle are not inherently MCP concerns.
The CLI may reuse `wf_mcp` service/config/store machinery in v1 because that is
where orchestration currently lives, but the package boundary should make it
clear that CLI is a separate front door. As shared stores/orchestration become
obvious, move them toward protocol-neutral packages such as `wf_artifacts`,
`wf_platform`, or a future `wf_runtime`.

## Non-Goals

Do not include app-domain nouns in CLI v1:

```text
wf scenario
wf decision
wf risk
wf approval
wf task
wf audit
wf metrics
```

Those can become examples, plugins, or higher-level applications later. The v1
CLI should expose workflow-platform primitives only.

Do not replace MCP. MCP still owns:

- in-client discovery
- remote control-plane tools
- resources/prompts/docs exposure
- interactive run/resume from MCP clients

Do not reimplement core workflow logic. CLI should call existing handlers or
shared services and use the same validation paths as MCP.

## CLI Framework

Use Typer for v1.

Reason: `wf` is intentionally grouped by lifecycle area (`cap`, `draft`,
`deploy`, `run`, etc.). Typer gives cleaner command-group composition, typed
options, help output, and future shell completion without building a large
manual `argparse` layer. The extra dependency is acceptable because the CLI is a
first-class front door, not a tiny debug script.

`pyproject.toml` should add:

```toml
dependencies = [
    "typer>=0.16",
]
```

Use Typer only at the CLI boundary. Command implementations should still call
plain functions/handlers so they remain testable without Typer.

## Package Shape

Initial layout:

```text
src/wf_cli/
  __init__.py
  app.py
  context.py
  io.py
  commands/
    __init__.py
    caps.py
    drafts.py
    artifacts.py
    deployments.py
    runs.py
    docs.py
    schema.py
    explain.py
```

Responsibilities:

- `app.py`
  - owns CLI entrypoint and command registration
  - exposes `main()`

- `context.py`
  - loads config/store roots
  - constructs the service/handler objects needed by commands
  - may use `wf_mcp` machinery in v1
  - should hide that dependency from command modules where practical

- `io.py`
  - parses `--input`, `--input-file`, and stdin
  - formats output as JSON by default
  - supports compact/id/table formats later
  - centralizes error output shape

- `commands/*`
  - one command group per workflow mental model
  - thin wrappers over handlers/services
  - no business logic that should live in workflow/platform packages

## Entry Points

`pyproject.toml` should eventually expose:

```toml
[project.scripts]
wf = "wf_cli.app:main"
wf-mcp = "wf_mcp.cli:main"
```

`wf-mcp` remains the MCP server CLI.

`wf` becomes the workflow platform CLI.

## V1 Command Surface

V1 should stay small:

```text
wf cap      list | inspect | call
wf draft    list | inspect | create-from-capability | patch | validate | save | delete
wf artifact list | inspect
wf deploy   list | inspect | save | delete | validate
wf run      start | resume | inspect | trace
wf docs     list | read
wf schema   <command>
wf explain  <error-json-or-code>
```

Potential follow-up commands after v1:

```text
wf draft step add
wf draft route set
wf draft output set
wf draft field add
```

These targeted authoring helpers should become the happy path over raw JSON
Patch, but raw patch stays as the escape hatch.

## Input Model

Every mutating command should support:

```bash
--input '<json>'
--input-file payload.json
```

Simple commands may also expose flags:

```bash
wf deploy validate echo.default --live
wf run trace run_123 --from 0 --limit 50
```

Rules:

- JSON output is default.
- File input is preferred for large payloads.
- Stdin support can be added after `--input-file`.
- No interactive prompts in v1 unless explicitly requested later.
- Mutating commands should eventually support `--dry-run`.

## Output Model

Default output is JSON:

```bash
wf run start echo.default --input-file input.json
```

returns the same conceptual shape as the workflow MCP tool:

```json
{
  "deployment_id": "echo.default",
  "status": "completed",
  "run_id": "run_123",
  "output": {},
  "diagnostics": [],
  "next_actions": {}
}
```

Output format policy:

```text
--format json       # default, complete machine-readable payload
--format compact    # terse human/agent summary where useful
--format ids        # identifier-only output for list/discovery commands
--format markdown   # prose-oriented output for explain/docs commands
```

Do not add every format to every command. `json` is always valid. `compact` and
`ids` are useful for list/discovery commands such as `cap list`, `draft list`,
`artifact list`, and `deploy list`. `markdown` is useful for prose surfaces such
as `explain` and `docs read`. Do not implement `table` in v1; agents do not need
it, and it creates formatting maintenance before the command contracts are
stable.

The concrete implementation plans should state the formats supported by each
command they add. Prefer a shared CLI formatting helper over per-command string
formatting once more than one command needs the same non-JSON shape.

## Lifecycle Flow

The CLI should make this flow easy:

```bash
wf cap inspect everything.default.echo

wf draft create-from-capability \
  --workspace echo_probe \
  --capability everything.default.echo

wf draft inspect echo_probe
wf draft patch echo_probe --input-file patch.json
wf draft validate echo_probe

wf draft save echo_probe \
  --artifact echo_probe \
  --version 1 \
  --title "Echo Probe"

wf deploy save echo_probe.default \
  --artifact echo_probe \
  --version 1 \
  --binding everything=everything.default

wf deploy validate echo_probe.default --live
wf run start echo_probe.default --input-file input.json
wf run inspect run_123
wf run trace run_123 --from 0 --limit 25
```

This maps directly to the current MCP workflow lifecycle while avoiding long
chains of schema-heavy MCP calls.

## Store And Config Boundary

V1 can reuse `wf_mcp` configuration and service construction.

That is pragmatic because `wf_mcp` currently owns:

- connection config
- source registration
- workflow surface handlers
- artifact/run store wiring
- some admin/control behavior

But this is not the desired long-term boundary.

As the CLI implementation touches these areas, prefer small refactors that move
protocol-neutral pieces out of `wf_mcp`:

- artifact/run store protocols and file stores should remain or move under
  `wf_artifacts`
- source/capability inventory models should remain or move under `wf_platform`
- workflow lifecycle orchestration may eventually deserve a protocol-neutral
  package if both MCP and CLI depend on it heavily

Do not do a large extraction before the CLI exists. Move shared code only when a
CLI command needs it and the seam is obvious.

## Skill Integration

The CLI should eventually generate skill-facing help:

```bash
wf --help-markdown
wf docs read workflow-lifecycle
wf schema draft create-from-capability
```

The skill should teach the lifecycle and prefer CLI commands for authoring:

1. inspect capability
2. create draft
3. inspect draft
4. patch or use targeted draft commands
5. validate draft
6. save artifact
7. save deployment
8. validate deployment
9. run
10. inspect trace only with a bounded range

The CLI does not need to generate the full skill in v1. A static skill can come
first, then `wf --help-markdown` can keep it synchronized later.

## Error Handling

CLI errors should be JSON by default:

```json
{
  "ok": false,
  "error": {
    "code": "deployment_unrunnable",
    "message": "Deployment is not runnable.",
    "diagnostics": [],
    "next_actions": {}
  }
}
```

Successful commands can return the raw handler payload plus an implicit
`ok=true` later if useful. Do not wrap successful payloads in v1 unless there is
a clear need; preserving existing handler shapes is more valuable.

`wf explain <error-json-or-code>` is useful, but it can be deferred until common
error shapes stabilize.

## Explain Registry

`wf explain` should not be a giant FAQ and should not be a freeform AI
explainer. It should be a small docs-backed registry of explanation cards keyed
by stable diagnostic codes and common CLI error codes.

Examples:

```bash
wf explain source_missing
wf explain source_missing --format json
wf explain source_missing --format markdown
wf explain schema_changed
wf explain deployment_unrunnable
wf explain --input-file error.json
wf explain --stdin
wf explain --list
```

Expected JSON shape:

```json
{
  "code": "source_missing",
  "summary": "A required logical source is not available or not bound.",
  "why_it_happens": [
    "The deployment references a logical source that has no concrete binding.",
    "The concrete source is disabled or missing from the current config."
  ],
  "how_to_fix": [
    "Run wf deploy inspect <deployment_id>.",
    "Check deployment bindings.",
    "Run wf cap list to confirm the source exists.",
    "Run wf deploy validate <deployment_id> --live."
  ],
  "related_docs": [
    "wf://docs/troubleshooting#source_missing"
  ]
}
```

Implementation shape:

```text
src/wf_cli/explain/
  __init__.py
  registry.py
  entries.py
  parser.py
```

Responsibilities:

- `entries.py`
  - owns curated explanation cards
  - no runtime workflow logic

- `registry.py`
  - maps code strings to explanation entries
  - supports `list` and exact lookup

- `parser.py`
  - extracts diagnostic codes from CLI/MCP-style JSON payloads
  - understands `diagnostics[]`, `{error: {code}}`, and direct code strings

V1 should support exact code lookup and JSON payload parsing only. Fuzzy search,
ranking, and generated prose can come later if they are actually needed.

`wf explain --list` should return a lean index, not full cards:

```json
{
  "entries": [
    {
      "code": "source_missing",
      "summary": "A required logical source is not available or not bound."
    },
    {
      "code": "schema_changed",
      "summary": "A saved dependency schema no longer matches the live capability."
    }
  ]
}
```

Use `wf explain <code>` for the full card.

`--format` applies to both full cards and list output:

```text
--format json       # default, machine-readable
--format markdown   # agent/human-readable prose
--format compact    # one-line summaries
```

This makes it easy to produce a small text/markdown handoff without forcing an
agent to parse JSON when prose is the better medium.

The same registry can later back MCP resources:

```text
wf://explain/source_missing
wf://explain/schema_changed
```

## First Implementation Slice

Implementation should happen as separate focused plans/chats. Do not ask one
agent to build the whole CLI at once.

### Slice 1: CLI Foundation

Create the shell of the CLI:

```text
src/wf_cli package
Typer app
wf console script
command group skeletons
shared context/config loader
JSON input/output helpers
```

This slice should not implement real workflow commands. Its job is to prove the
package, dependency, entrypoint, and test harness are clean.

### Slice 2: Run And Deploy Commands

Implement the first useful vertical slice:

```text
wf deploy validate
wf run start
wf run inspect
wf run trace
```

Reason:

- These already have strong handler support.
- They exercise store/config loading.
- They prove the CLI can operate as a second front door without solving draft
  authoring immediately.
- They expose `next_actions`, which makes the CLI self-guiding for agents.

### Slice 3: Explain Registry

Add docs-backed explanations:

```text
wf explain <code>
wf explain --input-file error.json
wf explain --stdin
wf explain --list
wf explain --format json|markdown|compact
```

Start with the common deployment/source diagnostics:

```text
source_missing
source_unreachable
binding_missing
capability_missing
schema_changed
deployment_unrunnable
```

This slice should build the registry and parser, not a giant FAQ.

### Slice 4: Discovery And Draft Lifecycle

Add capability discovery and draft authoring commands:

```text
wf cap list
wf cap inspect
wf draft list
wf draft inspect
wf draft create-from-capability
wf draft patch
wf draft validate
wf draft save
wf deploy save
wf deploy delete
```

This slice completes the minimum authoring loop. Targeted authoring helpers such
as `wf draft step add`, `wf draft route set`, and `wf draft output set` should
follow only after raw lifecycle coverage is proven.

The Slice 4 implementation plan should include the per-command output contract.
At minimum, list-style commands should support `--format json` and may support
`--format ids` or `--format compact` when the returned identifiers are stable.
Inspect, validate, save, delete, and patch commands should remain JSON-only
unless a concrete agent workflow benefits from another format.

## Testing

Use focused CLI tests that call `main()` or the app runner without spawning a
subprocess where possible.

Coverage goals:

- command parses JSON input
- command parses file input
- command emits JSON output
- non-zero exit on validation failure where appropriate
- deployment/run commands share handler behavior with MCP tests
- trace command requires bounded range

Do not assert whole JSON objects unless the command is intentionally a stable
contract. Prefer field assertions.

## Open Questions

1. Should CLI read the same config path as `wf-mcp` by default?
   - Recommendation: yes for v1. A single config/store root avoids confusion.

2. Should `wf` default to the current working directory store or configured
   store?
   - Recommendation: use explicit config/store resolution from existing
     `wf_mcp` paths first. Add cwd-local project mode later if needed.

3. Should CLI commands return exactly handler payloads or wrap in `{ok, data}`?
   - Recommendation: return handler payloads for success; use structured error
     payloads for failures.

## Approval Check

This spec intentionally chooses:

- new `wf_cli` package
- Typer as the CLI framework
- platform-only command surface
- pragmatic v1 dependency on `wf_mcp`
- incremental extraction of shared store/orchestration code
- JSON-first output
- run/deploy first slice before draft authoring helpers

If these choices hold, the next step is a focused implementation plan for the
first slice.
