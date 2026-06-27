# Draft Semantic Authoring Boundary

Date: 2026-06-27

Status: Approved for implementation planning. Canonical Path Strings section implemented.

Related:

- [Workflow drafts](../../workflow_drafts.md)
- [`wf_authoring` control flow](../../wf_authoring_control_flow.md)
- [Workflow API architecture](../../wf_api_architecture.md)
- [Current roadmap](../../current_roadmap.md)

## Purpose

Define a stable boundary between the persisted draft document, revisioned draft
workspaces, and capability-aware authoring operations intended for agents.

The draft system must remain one authoring model rather than becoming a second
workflow language beside `WorkflowBuilder`. Semantic operations therefore use
the same control-flow vocabulary as `WorkflowBuilder`, but lower each intent to
one atomic patch against the persisted `WorkflowDraft` representation.

## Current Problem

The current `WorkflowDraftApi` owns several distinct responsibilities:

- draft parsing, validation, and compilation;
- revisioned workspace lifecycle and JSON Patch application;
- low-level focused document edits;
- capability lookup and schema projection;
- compound authoring operations such as adding a capability step.

The responsibilities are individually valid, but keeping them in one service
obscures the boundary and allows semantic behavior to diverge from
`WorkflowBuilder`. The existing `add_step_from_capability` demonstrates this:
it writes one outgoing route even when the capability declares multiple
outcomes, producing a draft that immediately fails validation.

## Core Decisions

### One Persisted Authoring Representation

`WorkflowDraft` remains the only persisted authoring representation. It is a
patch-friendly intermediate form with keyed `steps`, `routes`, schemas, and
explicit bindings. `RawWorkflowPlan` remains the normalized execution model.

```text
semantic authoring intent
  -> atomic WorkflowDraft patch
  -> revision check
  -> compile and validate
  -> persisted WorkflowDraft workspace
  -> RawWorkflowPlan projection
```

Semantic operations do not persist builder objects, create an additional graph
model, or modify raw plans in place.

### Separate Semantic Authoring Service

Introduce `WorkflowDraftAuthoringApi` as a sibling of `WorkflowDraftApi`.

`WorkflowDraftApi` owns:

- workspace create, get, list, delete, and revision handling;
- draft validation and compilation;
- raw JSON Patch;
- low-level focused document edits;
- read-only projection of a stored workspace to `RawWorkflowPlan`.

`WorkflowDraftAuthoringApi` owns:

- capability-aware draft bootstrap;
- semantic construction of draft step kinds;
- adding a capability-backed `use` step;
- projecting and binding capability outputs into state;
- `branch` and `handle` semantic routing operations.

`WorkflowDraftAuthoringApi` depends on `WorkflowDraftApi` for workspace access
and patch application. It must not write the workspace store directly. Every
semantic operation produces one patch and consumes one revision.

`WorkflowApi` continues to expose one protocol-neutral facade. RPC, MCP, and CLI
clients do not need to know about the internal service split.

The service boundary is intentionally not capability-only. The current draft
model also represents `end`, `condition`, `interrupt`, `foreach`, `join`,
`when`, `choose`, and `match` steps, and core may gain more step kinds. This
slice adds semantic operations only where required, but new step-kind helpers
belong in `WorkflowDraftAuthoringApi` rather than a parallel authoring system.

### Match `WorkflowBuilder` Vocabulary

The semantic draft surface uses the established authoring terms:

- `branch`: connect several outcomes from one existing step to targets;
- `handle`: connect several source-step/outcome pairs to one shared target.

These operations add or replace edges only. They do not create condition steps,
wait for concurrent branches, or implement join semantics. `match`, `when`, and
`choose` remain outside this first slice.

## Public Operation Levels

The public draft surface is documented in descending order of preference.

### Semantic Authoring Operations

- `create-from-capability`
- `add-step-from-capability`
- `bind`
- `branch`
- `handle`

These operations understand capability definitions, schemas, outcomes, or
graph intent. They are the preferred agent authoring surface.

### Low-Level Focused Edits

- `set-name`
- `set-route`
- `set-input`
- `set-output`

These remain available for precise repairs. `set-input` and `set-output` do
not project workflow schemas; callers should prefer `bind` when a capability
input/output should also declare the matching workflow input, state, or output
schema.

### Escape Hatch

`patch` remains the RFC 6902 escape hatch for structural edits that semantic or
focused operations do not cover.

### Lifecycle And Projection

- `list`
- `inspect`
- `validate`
- `compile`
- `save`
- `delete`

These operations manage or inspect the workspace rather than expressing graph
authoring intent.

## Operation Contracts

### Add Step From Capability

`add-step-from-capability` atomically adds:

- one capability-backed `use` step;
- explicit input bindings;
- output-to-state bindings and required state schema projection;
- an optional incoming route;
- the complete outgoing route map.

The outgoing CLI option is repeatable:

```powershell
wf draft add-step-from-capability WORKSPACE `
  --revision 4 `
  --step second_echo `
  --capability everything.default.echo `
  --route ok=next `
  --route error=tool_error
```

When the caller supplies no routes and the capability declares exactly one
outcome, the operation infers that outcome, regardless of its name, and routes
it to `__end__`. If capability metadata declares no outcomes, the inferred
outcome is `ok`. When a capability has multiple known outcomes, the caller must
provide a target for every outcome. Missing or unknown outcomes reject the
operation before mutation and report the declared outcomes. Callers can always
override the target by supplying an explicit route.

The current singular `route_outcome` and `route_to` shape has no known external
caller or persisted-data dependency and is replaced rather than retained as
ghost compatibility behavior.

### Branch

`branch` applies several outcome routes from one existing step in one revision:

```powershell
wf draft branch WORKSPACE --revision 5 --step classify `
  --route send=send_email `
  --route skip=__end__ `
  --route error=tool_error
```

Supplied outcomes add or replace their route. Routes for outcomes omitted from
the request remain unchanged. The operation rejects an empty route map, unknown
source step, unknown declared outcome, or malformed target before mutation.
Normal workflow validation remains responsible for missing required outcomes,
unknown target steps, and broader graph consistency.

### Handle

`handle` redirects several source-step/outcome pairs to one shared target:

```powershell
wf draft handle WORKSPACE --revision 6 --to tool_error `
  --branch lookup:error `
  --branch transform:error
```

The transport request uses structured pairs rather than encoded strings. The
CLI parses each `STEP:OUTCOME` value at the final colon and rejects malformed
values before making the request. Existing routes unrelated to the supplied
pairs remain unchanged.

`handle` is not a join. It creates ordinary directed edges to one target.

### Bind

`bind` is the capability-aware schema propagation operation. It projects the
selected capability local input/output property and required `$defs` into the
workflow input, state, or output schema, then merges the matching step input or
output binding in the same revision.

```powershell
wf draft bind WORKSPACE --revision 4 --step wait `
  --from input.simulate `
  --to local.simulate

wf draft bind WORKSPACE --revision 5 --step wait `
  --from local.after `
  --to state.after
```

The partial `add-state-from-output` operation is removed from API, RPC, MCP,
CLI, docs, and skills. It was superseded before acquiring a real caller or
persisted-data contract.

### Compile A Stored Workspace

Add a read-only workspace projection:

```powershell
wf draft compile WORKSPACE
```

The server operation:

1. reads the stored workspace;
2. validates it in memory against current capability definitions;
3. compiles it through the existing draft adapter;
4. returns `compiled_plan` and required capability metadata.

The CLI prints only the bare `compiled_plan` JSON so it can be inspected or
piped directly into another command. The operation does not save an artifact,
refresh stored diagnostics, increment the revision, or otherwise mutate the
workspace.

An invalid workspace returns structured diagnostics and a nonzero CLI exit. It
must not emit a partial raw plan.

## Validation And Error Behavior

All semantic mutations use the current workspace revision. A stale revision,
malformed request, unknown capability, or semantic precondition failure leaves
the workspace unchanged.

Once a semantic patch is constructed, it passes through the existing workspace
patch path. That path performs the revision check, draft parsing, compilation,
structural validation, persistence, and refreshed diagnostics.

Known request-local mistakes should fail before mutation with specific data:

- multi-outcome step missing routes: include missing and declared outcomes;
- branch with unknown outcome: include the step's declared outcomes;
- handle with unknown source step: identify the missing step;
- duplicate route or branch values in one CLI invocation: reject as ambiguous;
- invalid compile: return the same structured diagnostic vocabulary as draft
  validation.

Draft workspaces may remain invalid during iterative low-level editing. Semantic
operations should avoid creating a known-invalid result when all required
information is already available in the request and capability catalog.

## Transport Shape

The protocol-neutral API uses mappings and structured records:

- branch routes: `dict[str, str]` mapping outcome to target;
- handle branches: a list of `{step_id, outcome}` records plus one target;
- add-step routes: `dict[str, str]` mapping every declared outcome to target.

RPC request models and MCP request models mirror those shapes. CLI parsing is a
front-end concern and must not leak encoded `STEP:OUTCOME` strings into the
application API.

## Canonical Path Strings

Authoring surfaces use one canonical TOML-key path grammar. Examples include:

```text
state.report.title
input."customer.name"
local.items
```

The underlying `GraphSourcePath`, `StatePath`, and `LocalPath` models remain
structured typed values. Strings are the public and serialized representation;
the models parse those strings once at their boundary.

Move TOML-key parsing from the `wf_authoring` convenience layer into `wf_core`
so CLI, RPC, MCP, drafts, raw plans, and Python authoring use the same parser and
formatter. The shared grammar must support quoted TOML keys for literal dots,
spaces, and other non-bare segments. Parse errors identify the complete input
and recommend quoting the invalid segment.

Pydantic JSON schemas advertise path strings rather than the structural
`{root, parts}` object. Serializers emit canonical strings. Validators continue
to accept the structural object only as a read-compatibility path for existing
persisted drafts, artifacts, and runs; new public examples and writes use
strings. This is compatibility for real stored data, not a second documented
syntax.

## Compatibility And Migration

No workflow semantics or draft field layout changes. The serialized path
representation changes from structural objects to canonical strings. Existing
workspaces, artifacts, deployments, and runs remain readable: their path
objects are accepted on input and become canonical strings when a containing
record is rewritten.

Low-level operations remain available. The migration changes only compound
operation signatures and removes the unused partial schema helper. Repository
callers, tests, docs, and skills are updated in the same slice. No compatibility
shim is added without a real external caller.

## Testing Strategy

### Domain And Service Tests

- branch merges supplied routes and preserves unrelated routes;
- handle updates several source routes atomically;
- malformed requests and stale revisions do not mutate the workspace;
- multi-outcome add-step requires complete routes;
- route inference chooses the sole declared outcome even when it is not `ok`;
- absent outcome metadata falls back to `ok`;
- an inferred route targets `__end__` unless explicitly overridden;
- output binding still projects referenced schema definitions;
- all path models parse and serialize the canonical TOML-key string grammar;
- structural path objects remain readable but are not emitted;
- stored-workspace compile equals `compile_workflow_draft` output;
- compile does not change revision, timestamps, status, or diagnostics.

### Surface Tests

- RPC and client methods preserve structured route data;
- MCP tools expose branch, handle, and workspace compile;
- CLI repeatable options parse into the protocol-neutral request shape;
- CLI compile prints only the raw plan and exits nonzero for invalid drafts;
- help text distinguishes semantic operations, low-level edits, and JSON Patch.

### Integration Regression

Build a two-step workflow where the second capability declares `ok` and
`error`. Add it with complete routes, save the artifact and deployment, run it,
and verify both steps execute without requiring a follow-up `set-route` repair.

## Non-Goals

- adding `match`, `when`, or `choose` draft commands in this slice;
- changing workflow semantics or the `WorkflowDraft` field layout;
- replacing JSON Patch;
- treating `handle` as synchronization or join behavior;
- automatic semantic compatibility analysis between connected schemas;
- saving artifacts as a side effect of compile.
