# wf_api Extraction Mapping Prompt

You are investigating the codebase only. Do not edit files.

Goal: map how the current workflow application surface is implemented so we can extract a protocol-neutral `wf_api` package without breaking MCP, CLI, stores, or tests.

The current suspicion:

- `src/wf_mcp/workflow_surface/handlers.py` is a large application-service class.
- It depends on `WfMcpService`, which is also broad.
- We need to understand whether to move the class first, split it first, or introduce smaller services/facades.

## Required Output

Write your findings to:

```text
docs/superpowers/research/2026-06-01-wf-api-extraction-map.md
```

Keep it structured and link-heavy. Do not paste huge code blocks. Use file paths, symbol names, and short notes.

## Investigation Scope

Focus on these files/symbols first:

```text
src/wf_mcp/workflow_surface/handlers.py
  WorkflowSurfaceHandlers

src/wf_mcp/broker/service/core.py
  WfMcpService

src/wf_mcp/workflow_surface/tools.py
  register_workflow_tools

src/wf_cli/context.py
  CliContext
  load_cli_context

src/wf_cli/commands/*.py

src/wf_artifacts/
src/wf_platform/
src/wf_core/
```

Use ripgrep/symbol search. Prefer precise symbol references over broad file dumps.

## Questions To Answer

### 1. What are the public operations?

List every `WorkflowSurfaceHandlers` public method and classify it:

```text
capabilities
drafts
artifacts
deployments
runs
explain/next-actions
internal helper accidentally public
```

For each method, record:

- method name
- input parameters
- return shape summary
- direct dependencies
- current callers/tests

### 2. What parts of `WfMcpService` does it actually use?

For each access from `WorkflowSurfaceHandlers` to `self.service`, record the member:

```text
self.service.artifact_store
self.service.draft_workspace_store
self.service.capability_sources
self.service._get_qualified_spec(...)
self.service._record_event(...)
...
```

Classify each dependency:

```text
artifact storage
draft storage
run storage
source/capability inventory
MCP connection/catalog
event bus
private helper currently being used
```

Flag private-method dependencies such as `_get_qualified_spec` or `_record_event`.

### 3. Which dependencies are MCP-specific vs protocol-neutral?

Create a table:

```text
Dependency | Package today | MCP-specific? | Should live in wf_artifacts/wf_platform/wf_api/wf_mcp?
```

Examples:

- artifact store likely protocol-neutral
- draft workspace store likely protocol-neutral
- source/capability refs likely protocol-neutral
- MCP connection config/adapters likely MCP-specific for now
- event bus may be platform-neutral

### 4. What is the safest extraction seam?

Compare these options:

#### Option A: Move class first

Move `WorkflowSurfaceHandlers` to `wf_api.service.WorkflowApi`, keep same constructor accepting `WfMcpService`.

Pros/cons.

#### Option B: Introduce API facade with ports

Create `WorkflowApi` that depends on a smaller `WorkflowApiBackend`/ports object instead of all `WfMcpService`, then adapt `WfMcpService` into that backend.

Pros/cons.

#### Option C: Split handlers by domain first

Split capabilities/drafts/artifacts/deployments/runs into separate classes before moving packages.

Pros/cons.

Recommend one first slice and explain why.

### 5. What should the target package shape be?

Propose a concrete package layout, for example:

```text
src/wf_api/
  __init__.py
  service.py
  backend.py
  capabilities.py
  drafts.py
  artifacts.py
  deployments.py
  runs.py
  models.py
```

Do not overdesign. Identify which files are needed in the first slice vs later.

### 6. What tests protect the extraction?

List existing tests that must continue to pass, grouped by package:

```text
tests/wf_mcp/workflow_surface/*
tests/wf_cli/*
tests/wf_mcp/test_server.py
...
```

Identify any missing tests needed before extraction.

### 7. What code should not move yet?

Explicitly list things that should stay in `wf_mcp` for now:

- MCP transport/proxy/runtime/session code
- FastMCP registration tools
- connection adapters if not protocol-neutral yet
- broker server construction

### 8. Risks and weirdness

Call out:

- circular import risks
- private method dependencies
- store ownership ambiguity
- naming confusion
- tests that monkeypatch `wf_cli.commands.*.load_cli_context`
- anything that would make FastAPI later harder or easier

## Output Format

Use this exact outline:

```markdown
# wf_api Extraction Map

## Executive Summary

## Public Operation Inventory

## WfMcpService Dependency Inventory

## Protocol-Neutral vs MCP-Specific Dependencies

## Extraction Options

## Recommended First Slice

## Proposed Package Shape

## Test Coverage

## Things To Keep In wf_mcp For Now

## Risks And Open Questions

## Suggested Next Plan
```

## Constraints

- Do not edit code.
- Do not propose FastAPI implementation yet.
- Keep current process-local behavior as the default.
- Assume `wf_mcp` and `wf_cli` should become adapters over the same process-local API.
- Prefer small, behavior-preserving extraction steps over a large rewrite.
