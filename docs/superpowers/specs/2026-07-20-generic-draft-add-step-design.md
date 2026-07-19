# Generic Draft Step Authoring Design

**Status:** Proposed

**Date:** 2026-07-20

## Problem

Draft authoring has a focused helper for capability-backed `node` steps, but
the other canonical workflow step kinds have no equivalent application or RPC
operation. Callers can patch raw draft JSON, but that bypasses the product's
typed authoring vocabulary and forces agents to hand-build JSON Patch paths.

The affected canonical step kinds are:

- `subgraph`
- `condition`
- `foreach`
- `join`
- `end`
- `interrupt`

The CLI also exposes only the flat `wf draft add-step --capability ...`
command. Extending that command with a `--type` switch would create one large
conditional form whose required and valid options change by step kind.

## Goals

- Add one generic, typed Python application operation for inserting any
  canonical `Step` into a draft workspace.
- Expose the operation through Python JSON-RPC and the Python RPC client.
- Replace the flat capability-only CLI command with a discoverable
  `wf draft add` command group.
- Preserve the capability helper's composed schema projection and binding
  behavior under `wf draft add capability`.
- Make each control-step command validate only the options relevant to that
  step kind.
- Keep one optimistic revision increment for the inserted step and any route
  wiring requested in the same command.
- Record implementation discoveries in `ISSUES.md`: strike resolved issues and
  add concrete bugs or missing product behavior found during the work.

## Non-Goals

- TypeScript or Effect RPC parity.
- RPC code generation.
- Web workflow authoring UI.
- New workflow step kinds or runtime semantics.
- Compatibility aliases for unused command shapes.
- Replacing the existing capability-composition helper with a raw node insert.

## Application API

Add a generic operation to the workflow API surface:

```python
async def add_step(
    *,
    workspace_id: str,
    revision: int,
    step: Step,
    route_from_step: str | None = None,
    route_from_outcome: str = "ok",
    routes: dict[str, str] | None = None,
) -> dict[str, Any]: ...
```

`step.id` is the canonical identifier. The operation does not accept a second
`step_id` that could disagree with the model.

The operation:

1. parses and validates the discriminated `Step` union before mutation;
2. rejects an existing step id;
3. inserts the canonical serialized step into the draft's `steps` object;
4. optionally routes one existing step outcome into the new step;
5. optionally records outgoing routes supplied for the new step; and
6. applies the complete change through one revision-checked draft patch.

Draft workspaces intentionally support invalid intermediate states. Therefore,
`add_step` does not require every declared outcome to be routed immediately.
When routes are supplied, it rejects outcomes that the inserted step cannot
emit. End steps reject outgoing routes. Full graph completeness remains the
responsibility of draft validation.

The existing capability-composition operation remains a distinct application
helper because it resolves a capability, projects schemas, constructs a
`NodeUse`, and creates bindings. It may reuse the generic insertion mechanics
internally, but its public behavior must not regress.

## JSON-RPC And Python Client

Add:

```text
workflow.draft_workspaces.add_step
```

Its parameter model mirrors the application operation. The `step` field uses
the canonical discriminated `Step` union rather than an unvalidated
`dict[str, Any]`. RPC errors continue through the existing
`WorkflowRpcError` translation boundary.

The Python RPC client implements the same method on the workflow API surface.
Round-trip tests cover every step variant so the transport cannot silently
drop aliases, schemas, policies, bindings, outcomes, or workflow references.

## CLI Shape

Create a Typer subgroup beneath `wf draft`:

```text
wf draft add capability
wf draft add interrupt
wf draft add condition
wf draft add foreach
wf draft add join
wf draft add end
wf draft add subgraph
```

The existing `wf draft add-step` command is removed rather than retained as a
ghost alias. Repository-owned docs, tests, skills, examples, and scripts are
migrated to `wf draft add capability`.

Every command shares these routing options where meaningful:

- workspace id argument;
- `--revision`;
- `--step`;
- optional `--from-step` and `--from-outcome`; and
- repeatable `--route OUTCOME=TARGET` for step kinds with outgoing outcomes.

The commands then expose only their own model fields:

- `capability`: capability name plus existing input and output binding flags;
- `interrupt`: kind, request/resume schema files, request/resume bindings, and
  repeatable outcomes;
- `condition`: a JSON condition document;
- `foreach`: source path, item context name, serial/concurrent mode, item-error
  policy, and concurrent limits;
- `join`: no additional step fields;
- `end`: workflow outcome and no outgoing routes; and
- `subgraph`: workflow reference, boundary schema files, bindings, and
  repeatable outcomes.

Compound model values use JSON files rather than dense inline JSON. Existing
map-style flags are reused for simple path bindings when their direction is
unambiguous. CLI help includes one valid example per command and directs users
to `wf draft validate` after editing.

## Validation And Errors

- Pydantic owns step-shape validation; CLI and RPC do not duplicate the core
  model rules.
- CLI parsing errors identify the invalid flag or file before making an API
  call.
- Application errors identify duplicate ids, missing incoming source steps,
  unsupported route outcomes, and forbidden end-step routes.
- Revision conflicts preserve the existing draft-workspace behavior.
- No command guesses missing routes or silently invents bindings.

## Tests

### Application

- Parameterized insertion for every `Step` variant.
- Atomic incoming and outgoing route wiring.
- Duplicate id rejection without mutation.
- Unknown outcome and end-route rejection without mutation.
- Invalid intermediate drafts remain persistable and validate diagnostically.

### RPC And Client

- Parameter model rejects malformed discriminators and variant fields.
- App round trip for every step kind.
- Client method emits the exact method name and canonical payload.
- RPC failures occur before draft mutation.

### CLI

- The `wf draft add` help lists all seven commands.
- Per-command help exposes only relevant options.
- Each command constructs the expected canonical step and route payload.
- `add capability` preserves existing composed authoring behavior.
- Removed `add-step` references are absent from live docs and tests.

## Documentation And Issue Tracking

- Update CLI docs, agent skills, examples, and roadmap references to the new
  command shape.
- Mark the dedicated-step-authoring issue in `ISSUES.md` resolved when all six
  non-capability commands are covered.
- Add newly discovered defects to `ISSUES.md` only when they are concrete,
  reproducible, and outside this slice. Fix in-scope defects instead of merely
  documenting them.

## Deferred Work

A later parity slice may expose the full Python JSON-RPC suite through the
TypeScript Effect RPC package. That work should first add a machine-checked
method parity manifest. Whether schemas are generated should be decided from
the canonical Python registry and schema-export capabilities, not by generating
from duplicate handwritten TypeScript definitions.

## Acceptance Criteria

- Every canonical workflow step kind can be added through the application API,
  Python JSON-RPC, Python RPC client, and a type-specific CLI command.
- One generic `add_step` operation owns raw typed insertion.
- Capability-backed insertion retains schema projection and binding behavior.
- CLI vocabulary is grouped under `wf draft add` with no unneeded compatibility
  alias.
- Invalid requests fail before mutation and revision semantics remain atomic.
- Focused tests, type checking, formatting, and documentation checks pass.
