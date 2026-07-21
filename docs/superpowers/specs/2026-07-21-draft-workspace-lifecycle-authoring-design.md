# Draft Workspace Lifecycle Authoring Design

## Goal

Expose capability-free draft creation and focused workflow metadata edits across
the Python workflow surface, JSON-RPC, and `wf` CLI. An author must be able to
start with a control, interrupt, end, subgraph, or capability step without first
creating and removing an unrelated capability bootstrap.

## Problem

The canonical `WorkflowDraft` model already represents:

- workflow input, state, and output schemas;
- declared public outcomes;
- a mutable entry point;
- every supported draft step kind.

The transport-facing authoring interface does not expose all of those concepts.
`wf draft create` requires a capability, while changing `start`, schemas, or
workflow outcomes requires hand-written RFC 6902 patches. This makes the focused
interface shallower than both `WorkflowDraft` and `WorkflowBuilder`.

Draft workspaces already preserve invalid intermediate documents and return
structured diagnostics. Capability-free creation can therefore use the existing
incremental authoring model rather than inventing a placeholder capability or a
second transaction system.

## Scope

This slice adds three focused operations:

1. create an empty, capability-free draft workspace;
2. set the draft entry point;
3. replace any supplied workflow contract fields atomically.

Every operation is exposed through:

- `WorkflowApi` and `WorkflowDraftSurface`;
- Python JSON-RPC server models and methods;
- `RpcWorkflowApiClient`;
- local and remote `wf` CLI handlers;
- user-facing draft documentation and agent skills.

The MCP tool frontend remains unchanged in this slice. CLI-using agents gain the
new lifecycle operations through the local or remote workflow surface; native
MCP tool parity is a separate follow-up.

## Out Of Scope

This slice does not:

- add deep-merge semantics for JSON Schema;
- add field-selection or schema projection from capability contracts;
- replace focused path maps with canonical binding-list editors;
- add literal binding commands;
- add a general multi-operation authoring transaction;
- add or change MCP workflow tools, request models, or proxy tool inventories;
- expand the TypeScript Effect RPC operation catalog;
- add focused updates for step descriptions, retries, or timeouts;
- fix revision precedence in unrelated semantic edit helpers.

Those remain separate issues. Existing capability-aware schema projection stays
available and complements the explicit whole-contract operation.

## Interface

### Empty Workspace Creation

Add the transport-facing operation:

```python
async def create_empty_draft_workspace(
    *,
    workspace_id: str,
    name: str,
    title: str | None = None,
    input_schema: dict[str, Any] | None = None,
    state_schema: dict[str, Any] | None = None,
    output_schema: dict[str, Any] | None = None,
    outcomes: Sequence[str] = ("ok",),
) -> dict[str, Any]: ...
```

Omitted schemas become independent empty object schemas:

```json
{"type": "object", "properties": {}}
```

The operation stores this stable revision-1 draft shape:

```json
{
  "name": "report_workflow",
  "input_schema": {"type": "object", "properties": {}},
  "state_schema": {"type": "object", "properties": {}},
  "output_schema": {"type": "object", "properties": {}},
  "outcomes": ["ok"],
  "output": [],
  "start": "",
  "steps": {},
  "routes": {}
}
```

The empty entry point intentionally makes the workspace invalid. Creation still
succeeds, returns revision 1, and includes the existing structured validation
diagnostic. No placeholder node or capability is created.

Duplicate workspace IDs use the existing `workspace_exists` conflict result and
do not overwrite the stored workspace.

### Entry Point Edit

Add:

```python
async def set_draft_start(
    *,
    workspace_id: str,
    revision: int,
    step_id: str,
) -> dict[str, Any]: ...
```

The operation replaces `/start` in one revision. `step_id` must be non-empty,
but it may refer to a step that has not been added yet. A forward reference is
persisted and reported through normal invalid-draft diagnostics, matching the
existing incremental behavior of forward route targets.

### Workflow Contract Edit

Add:

```python
async def set_draft_contract(
    *,
    workspace_id: str,
    revision: int,
    input_schema: dict[str, Any] | None = None,
    state_schema: dict[str, Any] | None = None,
    output_schema: dict[str, Any] | None = None,
    outcomes: Sequence[str] | None = None,
) -> dict[str, Any]: ...
```

The operation replaces each supplied top-level field and preserves every
omitted field. All supplied replacements are applied by one JSON Patch call and
produce exactly one new workspace revision.

Schema documents are whole-field replacements, not deep merges. JSON Schema
keywords such as `required`, `$defs`, unions, and nested `properties` do not
have one safe generic merge rule. Callers that need field-level surgery retain
the existing raw JSON Patch operation. State reducer declarations remain schema
metadata and are preserved when supplied in a replacement `state_schema`; this
slice does not invent a separate reducer-edit model.

At least one contract field must be supplied. Supplied outcomes must contain at
least one non-empty, unique value. Invalid request envelopes fail before
mutation; structurally inconsistent but representable draft contracts are
persisted and reported through normal draft diagnostics.

## CLI

Broaden the existing command without breaking capability-backed callers:

```bash
# Capability-free creation
wf draft create report_ws --name report_workflow

# Existing behavior remains valid
wf draft create report_ws --capability docs.local.read_documents
```

Rules:

- `--capability` becomes optional.
- Without `--capability`, `--name` is required.
- With `--capability`, the current capability-bootstrap path and defaults stay
  unchanged.
- Optional schema files and repeated outcomes belong to capability-free
  creation only. The existing capability bootstrap remains the contract-derived
  convenience path.

Add focused commands:

```bash
wf draft set-start report_ws --revision 2 --step review

wf draft set-contract report_ws --revision 3 \
  --input-schema-file input.schema.json \
  --state-schema-file state.schema.json \
  --output-schema-file output.schema.json \
  --outcome ok \
  --outcome error
```

Each schema file must decode to a JSON object. Repeated `--outcome` flags replace
the complete outcomes list. Calling `set-contract` without any contract option
is a concise CLI input error and does not contact the server.

## JSON-RPC

Register distinct methods rather than overloading the existing capability
request model:

```text
workflow.draft_workspaces.create_empty
workflow.draft_workspaces.set_start
workflow.draft_workspaces.set_contract
```

Distinct request models keep method discovery and generated schemas explicit.
The remote client implements the same `WorkflowDraftSurface` interface as the
local `WorkflowApi`, so CLI behavior remains target-independent.

## Revision And Error Semantics

`set_draft_start` and `set_draft_contract` delegate mutation to the canonical
revisioned workspace patch operation. Therefore:

- stale revisions return `revision_conflict`;
- stale requests do not mutate the workspace;
- after a request envelope is valid, revision conflict is checked before
  validation that depends on current workspace content;
- forward references and other representable invalid states consume one
  revision and return diagnostics;
- replacing a field with an equal value still consumes one revision, matching
  ordinary JSON Patch behavior in this slice.

Request-envelope errors such as no supplied contract field, an empty outcome
list, duplicate outcomes, or a non-object schema are rejected before workspace
lookup and therefore may precede a stale-revision result. They never mutate the
workspace.

## Testing

Tests must cover each interface rather than only the lowest-level helper.

### Python API

- capability-free creation stores the exact stable skeleton;
- default schema objects are independent values;
- custom schemas, outcomes, name, and title are preserved;
- reducer metadata in a custom state schema is preserved unchanged;
- duplicate workspace IDs return `workspace_exists`;
- setting an existing start step can make a draft valid;
- setting a missing start step persists an invalid forward reference;
- a multi-field contract edit uses one revision;
- omitted contract fields remain byte-for-byte unchanged;
- stale start and contract edits return `revision_conflict` without mutation;
- empty or duplicate outcomes and empty contract edits do not mutate.

### JSON-RPC And Remote Client

- all three method names are registered;
- request models enforce field and outcome constraints;
- server methods call the workflow surface with exact arguments;
- the remote client emits the expected JSON-RPC params and decodes workspace
  results;
- remote conflict and invalid-draft results preserve the existing envelope.
- one remote JSON-RPC test executes the complete capability-free lifecycle,
  rather than testing only isolated method dispatch.

### CLI

- `wf draft create --name` uses capability-free creation locally and remotely;
- omitting both `--capability` and `--name` is rejected;
- existing `wf draft create --capability` tests remain green;
- schema files and outcomes are parsed exactly once;
- `set-start` and `set-contract` dispatch identical local and remote calls;
- empty contract invocation, non-object schema files, and duplicate outcomes
  produce compact parameter errors.

### End-To-End Authoring

Exercise this sequence once through the local `WorkflowApi` and once through
the remote JSON-RPC client:

1. create an empty workspace;
2. add a non-capability first step, such as `interrupt` or `when`;
3. set that step as the entry point;
4. add an `end` step with a non-`ok` outcome;
5. declare that outcome through `set_draft_contract`;
6. validate successfully without raw JSON Patch.

## Documentation

Update:

- `docs/workflow_drafts.md` with the capability-free lifecycle;
- `skills/wf-cli/SKILL.md` and `skills/wf-workflow/SKILL.md` with the new
  commands and when to use contract replacement versus schema projection;
- `docs/current_roadmap.md` with the completed implementation link after the
  code slice lands;
- `ISSUES.md` by checking the capability-free creation, start, outcomes, and
  schema-editing items only after their public surfaces and tests exist.

## Success Criteria

- A caller can create a draft workspace without naming a capability.
- The empty workspace has stable patch targets and honest invalid diagnostics.
- A caller can set a forward-referenced entry point through a focused command.
- A caller can replace any combination of workflow schemas and outcomes in one
  revision without deep-merge ambiguity.
- Local API, JSON-RPC, remote client, and CLI expose equivalent behavior.
- Existing capability-backed draft creation remains compatible.
- A control-first workflow can reach valid status without raw JSON Patch.
