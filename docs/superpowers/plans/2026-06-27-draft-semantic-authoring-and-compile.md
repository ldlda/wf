# Draft Semantic Authoring And Compile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separate semantic draft authoring from workspace lifecycle, add `branch` and `handle`, make capability-step routing complete, and expose read-only stored-workspace compilation.

**Architecture:** `WorkflowDraft` remains the only stored authoring document. A new `WorkflowDraftAuthoringApi` resolves capability metadata and lowers semantic intent to one atomic patch through `WorkflowDraftApi`; the latter retains lifecycle, validation, compilation, low-level edits, and JSON Patch. Public CLI, RPC, and MCP surfaces remain unified through `WorkflowApi`.

**Tech Stack:** Python 3.14, Pydantic v2, JSON Patch, Typer, JSON-RPC, FastMCP, pytest, Ruff, basedpyright.

**Prerequisite:** Complete `docs/superpowers/plans/2026-06-27-canonical-toml-path-strings.md` first.

---

### Task 1: Extract The Semantic Authoring Service Without Behavior Changes

**Files:**
- Create: `src/wf_api/draft_authoring.py`
- Create: `src/wf_api/draft_payloads.py`
- Modify: `src/wf_api/drafts.py`
- Modify: `src/wf_api/service.py`
- Test: `tests/wf_api/test_drafts_service.py`

- [ ] **Step 1: Add a facade delegation test**

Add a focused test asserting `WorkflowApi` constructs a sibling authoring
service and existing `bind_output_to_state` behavior still consumes one
revision.

- [ ] **Step 2: Extract shared draft payload helpers**

Move the existing `_draft_step`, `_escape_json_pointer`,
`_draft_input_bindings_payload`, `_draft_output_bindings_payload`, and
`_state_root_field` bodies unchanged into `src/wf_api/draft_payloads.py`.
Rename them to `draft_step`, `escape_json_pointer`, `input_bindings_payload`,
`output_bindings_payload`, and `state_root_field`, update both service imports,
and add short docstrings. Do not change serialized behavior in this extraction.

- [ ] **Step 3: Introduce `WorkflowDraftAuthoringApi`**

Use an explicit dependency on the lifecycle service:

```python
class WorkflowDraftAuthoringApi:
    """Capability-aware semantic edits over revisioned workflow drafts."""

    def __init__(
        self,
        context: WorkflowOperationContext,
        drafts: WorkflowDraftApi,
    ) -> None:
        self.context = context
        self.drafts = drafts
```

Move `create_minimal_draft_workspace`, `bind_output_to_state`, and
`add_step_from_capability` into this class. Each operation must call
`self.drafts.patch_draft_workspace` or another public lifecycle method rather
than accessing the store directly for mutation.

- [ ] **Step 4: Preserve the unified facade**

In `WorkflowApi.__init__`:

```python
self.drafts = WorkflowDraftApi(context)
self.draft_authoring = WorkflowDraftAuthoringApi(context, self.drafts)
```

Existing public delegates keep their names and forward semantic calls to
`self.draft_authoring`.

- [ ] **Step 5: Run focused tests**

Run: `uv run pytest tests/wf_api/test_drafts_service.py -q`

Expected: PASS with no public behavior change.

- [ ] **Step 6: Commit**

```bash
git add src/wf_api/draft_authoring.py src/wf_api/draft_payloads.py src/wf_api/drafts.py src/wf_api/service.py tests/wf_api/test_drafts_service.py
git commit -m "refactor: separate draft semantic authoring"
```

### Task 2: Remove The Superseded Partial State Projection Operation

**Files:**
- Modify: `src/wf_api/service.py`
- Modify: `src/wf_api/surface.py`
- Modify: `src/wf_transport_rpc_http/models.py`
- Modify: `src/wf_transport_rpc_http/methods/drafts.py`
- Modify: `src/wf_transport_rpc_http/client/drafts.py`
- Modify: `src/wf_transport_rpc_http/__init__.py`
- Modify: `src/wf_mcp/workflow_surface/models.py`
- Modify: `src/wf_mcp/workflow_surface/tools.py`
- Modify: `src/wf_cli/commands/drafts.py`
- Modify: affected draft tests in `tests/`

- [ ] **Step 1: Prove no production caller remains**

Run:

```powershell
rg -n 'add_state_schema_from_output|add-state-from-output' src tests docs skills
```

Expected: only the operation implementation, adapters, tests, and docs refer to
it; no independent production caller depends on it.

- [ ] **Step 2: Remove the operation end to end**

Delete `add_state_schema_from_output`, its request/params DTOs, RPC method,
client method, MCP tool, CLI command, exports, and dedicated tests. Do not add a
compatibility shim. Keep `bind_output_to_state` as the complete semantic
operation.

- [ ] **Step 3: Run surface import and help tests**

Run:

```bash
uv run pytest tests/wf_cli/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_mcp/server/test_config.py -q
```

Expected: PASS and no removed command/tool in enumerated surfaces.

- [ ] **Step 4: Commit**

```bash
git add src tests
git commit -m "refactor: remove partial draft state projection"
```

### Task 3: Add Atomic `branch` And `handle` Authoring Operations

**Files:**
- Modify: `src/wf_api/draft_authoring.py`
- Modify: `src/wf_api/service.py`
- Modify: `src/wf_api/surface.py`
- Modify: `src/wf_transport_rpc_http/models.py`
- Modify: `src/wf_transport_rpc_http/methods/drafts.py`
- Modify: `src/wf_transport_rpc_http/client/drafts.py`
- Modify: `src/wf_transport_rpc_http/__init__.py`
- Modify: `src/wf_mcp/workflow_surface/models.py`
- Modify: `src/wf_mcp/workflow_surface/tools.py`
- Modify: `src/wf_cli/commands/drafts.py`
- Test: `tests/wf_api/test_drafts_service.py`
- Test: `tests/wf_transport_rpc_http/test_app.py`
- Test: `tests/wf_transport_rpc_http/test_client.py`
- Test: `tests/wf_cli/test_remote_target.py`
- Test: `tests/wf_mcp/server/test_config.py`

- [ ] **Step 1: Write failing API tests**

Cover atomic route updates and preservation:

```python
result = await api.branch_draft(
    workspace_id="branching",
    revision=1,
    step_id="classify",
    routes={"ok": "next", "error": "tool_error"},
)
assert result["revision"] == 2
workspace = await api.get_draft_workspace(workspace_id="branching")
assert workspace["draft"]["routes"]["classify"] == {
    "ok": "next",
    "error": "tool_error",
    "retry": "retry_step",
}
```

Add a `handle_draft` test updating two source outcomes in one revision. Assert
empty mappings, duplicate CLI values, unknown source steps, and unknown declared
outcomes leave the workspace byte-for-byte unchanged.

- [ ] **Step 2: Implement semantic methods**

Use protocol-neutral signatures. `branch_draft` takes keyword-only
`workspace_id: str`, `revision: int`, `step_id: str`, and
`routes: dict[str, str]`. `handle_draft` takes keyword-only `workspace_id: str`,
`revision: int`, `branches: Sequence[DraftOutcomeRef]`, and `target: str`. Both
return `dict[str, Any]`.

Define `DraftOutcomeRef` as a small frozen Pydantic model or dataclass with
`step_id` and `outcome`. Validate request-local preconditions first, build one
JSON Patch list, then call `WorkflowDraftApi.patch_draft_workspace` once.

- [ ] **Step 3: Add transport models and methods**

RPC and MCP request models use structured branch records. Register:

```text
workflow.draft_workspaces.branch
workflow.draft_workspaces.handle
wf.workflow.branch_draft
wf.workflow.handle_draft
```

Extend `WorkflowDraftSurface` and the RPC client mixin with the exact API
signatures.

- [ ] **Step 4: Add CLI commands**

Expose:

```powershell
wf draft branch WORKSPACE --revision N --step STEP --route ok=next --route error=fail
wf draft handle WORKSPACE --revision N --to fail --branch lookup:error --branch transform:error
```

Parse route values with the existing strict `KEY=VALUE` utility. Parse branch
values at the final colon, reject duplicates, and send structured records.

- [ ] **Step 5: Run vertical-slice tests**

```bash
uv run pytest tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_remote_target.py tests/wf_mcp/server/test_config.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src tests
git commit -m "feat: add semantic draft branch and handle"
```

### Task 4: Make Capability-Step Routing Complete

**Files:**
- Modify: `src/wf_api/draft_authoring.py`
- Modify: `src/wf_api/service.py`
- Modify: `src/wf_api/surface.py`
- Modify: `src/wf_transport_rpc_http/models.py`
- Modify: `src/wf_transport_rpc_http/methods/drafts.py`
- Modify: `src/wf_transport_rpc_http/client/drafts.py`
- Modify: `src/wf_mcp/workflow_surface/models.py`
- Modify: `src/wf_mcp/workflow_surface/tools.py`
- Modify: `src/wf_cli/commands/drafts.py`
- Test: affected API/RPC/MCP/CLI draft tests

- [ ] **Step 1: Write failing routing-policy tests**

Cover three cases:

```python
# One declared outcome named "done", no routes supplied.
assert added_routes == {"done": "__end__"}

# No outcome metadata, no routes supplied.
assert added_routes == {"ok": "__end__"}

# Multiple declared outcomes, incomplete explicit routes.
with pytest.raises(ValueError, match="missing routes.*error"):
    await api.add_step_from_capability(
        workspace_id="multi",
        revision=1,
        step_id="echo",
        capability_name="demo.echo",
        routes={"ok": "__end__"},
    )
```

Also assert complete multi-outcome routes succeed in one revision.

- [ ] **Step 2: Replace singular route parameters**

Replace `route_outcome` and `route_to` with:

```python
routes: dict[str, str] | None = None
```

Resolve declared capability outcomes before mutation. Infer the sole outcome
regardless of name; use `ok` only when metadata supplies none. For multiple
declared outcomes, require exact coverage and report `declared_outcomes`,
`missing_outcomes`, and `unknown_outcomes` in the application error.

- [ ] **Step 3: Update all public adapters**

RPC and MCP accept a route mapping. CLI replaces singular `--outcome`/`--to`
with repeatable `--route OUTCOME=TARGET`. Update help to explain sole-outcome
inference and multi-outcome completeness.

- [ ] **Step 4: Run focused tests**

```bash
uv run pytest tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py tests/wf_mcp/server/test_config.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src tests
git commit -m "fix: require complete capability step routes"
```

### Task 5: Compile A Stored Draft Workspace Without Mutation

**Files:**
- Modify: `src/wf_api/drafts.py`
- Modify: `src/wf_api/service.py`
- Modify: `src/wf_api/surface.py`
- Modify: `src/wf_transport_rpc_http/models.py`
- Modify: `src/wf_transport_rpc_http/methods/drafts.py`
- Modify: `src/wf_transport_rpc_http/client/drafts.py`
- Modify: `src/wf_transport_rpc_http/__init__.py`
- Modify: `src/wf_mcp/workflow_surface/models.py`
- Modify: `src/wf_mcp/workflow_surface/tools.py`
- Modify: `src/wf_cli/commands/drafts.py`
- Test: affected API/RPC/MCP/CLI draft tests

- [ ] **Step 1: Write failing no-mutation API tests**

Capture the workspace before and after compilation:

```python
before = await api.get_draft_workspace(workspace_id="compile_me")
result = await api.compile_draft_workspace(workspace_id="compile_me")
after = await api.get_draft_workspace(workspace_id="compile_me")

assert result["compiled_plan"]["name"] == "compile_me"
assert result["required_capabilities"]
assert after == before
```

Add an invalid-workspace test asserting structured diagnostics and no
`compiled_plan`.

- [ ] **Step 2: Implement the read-only projection**

Add:

```python
async def compile_draft_workspace(self, *, workspace_id: str) -> dict[str, Any]:
    workspace = self._draft_store().get_workspace(workspace_id)
    validation = await self.validate_draft(draft=workspace.draft)
    if validation["status"] != "valid":
        return validation
    return await self.compile_draft(draft=workspace.draft)
```

Do not call `validate_draft_workspace`, because that operation refreshes stored
status and diagnostics.

- [ ] **Step 3: Expose RPC and MCP operations**

Register:

```text
workflow.draft_workspaces.compile
wf.workflow.compile_draft_workspace
```

Return the application envelope containing `compiled_plan` and
`required_capabilities`.

- [ ] **Step 4: Add the CLI projection**

Expose `wf draft compile WORKSPACE`. On success print only
`result["compiled_plan"]`. On invalid status, print the structured diagnostic
envelope to stderr and exit nonzero. Do not add an output-file option.

- [ ] **Step 5: Run focused tests**

```bash
uv run pytest tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py tests/wf_mcp/workflow_surface/test_drafts.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src tests
git commit -m "feat: compile stored draft workspaces"
```

### Task 6: Documentation, Skills, And End-To-End Regression

**Files:**
- Modify: `docs/workflow_drafts.md`
- Modify: `docs/wf_cli.md`
- Modify: `docs/wf_authoring_control_flow.md`
- Modify: `skills/wf-cli/SKILL.md`
- Modify: `skills/wf-workflow/SKILL.md`
- Modify: `skills/wf-workflow/references/draft-workspaces.md`
- Modify: `skills/wf-workflow/references/workflow-lifecycle.md`
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-27-draft-semantic-authoring-boundary.md`
- Test: `tests/wf_cli/test_remote_target.py`
- Move after completion: `docs/superpowers/plans/2026-06-27-draft-semantic-authoring-and-compile.md` -> `docs/historical/superpowers/plans/2026-06-27-draft-semantic-authoring-and-compile.md`

- [ ] **Step 1: Add a two-step multi-outcome integration regression**

Use the running RPC test fixture or local static server to:

1. create a workspace from a capability;
2. add a second capability declaring `ok` and `error` with both routes;
3. validate without a follow-up `set-route` call;
4. save the artifact and deployment;
5. run it and assert two trace frames completed.

This test must fail against the old singular-route helper.

- [ ] **Step 2: Reorganize public guidance by operation level**

Document semantic operations first, focused edits second, `patch` last. Explain
that `branch` and `handle` mirror `WorkflowBuilder` but mutate `WorkflowDraft`.
Document `compile` as read-only and show that it prints a raw plan without
saving an artifact.

- [ ] **Step 3: Document extensibility without implementing extra step kinds**

State that `WorkflowDraftAuthoringApi` is the home for future semantic helpers
for `interrupt`, `foreach`, condition, join/end, and future core step kinds.
Do not add commands for them in this slice.

- [ ] **Step 4: Update status documents**

Mark the design implemented, record the completed roadmap item, update live
links, and archive this plan.

- [ ] **Step 5: Run final verification**

```bash
uv run pytest tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py tests/wf_mcp/workflow_surface/test_drafts.py tests/wf_mcp/server/test_config.py -q
uv run ruff check
uv run ruff format --check
uv run basedpyright --level error
git diff --check
```

Expected: all tests pass, Ruff is clean, basedpyright reports zero errors, and
there are no whitespace errors.

- [ ] **Step 6: Archive and commit**

```bash
git mv docs/superpowers/plans/2026-06-27-draft-semantic-authoring-and-compile.md docs/historical/superpowers/plans/2026-06-27-draft-semantic-authoring-and-compile.md
git add docs skills tests
git commit -m "docs: record semantic draft authoring surface"
```
