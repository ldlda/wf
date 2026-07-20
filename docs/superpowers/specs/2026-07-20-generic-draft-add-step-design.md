# Generic Draft Step Authoring Design

**Status:** Approved

**Date:** 2026-07-20

## Problem

Draft workspaces expose a composed helper for capability-backed `use` steps,
but no typed application or RPC operation can insert the other draft step
variants. Callers must patch raw draft JSON, which bypasses the semantic
authoring boundary and forces agents to construct JSON Pointer paths.

The CLI has the same gap. Its flat `wf draft add-step --capability NAME`
command only supports capability steps. Adding a `--type` switch would produce
one conditional form whose required options change by step kind.

Two model gaps also prevent full draft/core parity:

- `DraftInterruptPayload` cannot preserve `request_schema` or `resume_schema`.
- `DraftStep` cannot represent a canonical `SubgraphNode` boundary.

## Goals

- Add one generic typed Python application operation for inserting any
  `DraftStep` into a workspace.
- Preserve step identifiers as keys in `WorkflowDraft.steps` rather than
  duplicating them inside step payloads.
- Add typed interrupt contracts and subgraph boundaries to the draft model and
  adapter.
- Expose generic insertion through Python JSON-RPC and the Python RPC client.
- Replace the flat capability command with a discoverable `wf draft add`
  subgroup covering every draft authoring variant.
- Preserve capability schema projection, binding, and route behavior under
  `wf draft add capability`.
- Apply the inserted step and requested route wiring in one optimistic
  revision.
- Keep `ISSUES.md` accurate as parity gaps are resolved or discovered.

## Non-Goals

- TypeScript or Effect RPC parity.
- RPC code generation.
- Web workflow authoring UI.
- New runtime semantics.
- Resolving or loading saved subgraph artifacts while parsing a draft.
- Compatibility aliases for the unused `wf draft add-step` shape.
- Replacing capability composition with raw `DraftUseStep` insertion.

## Canonical Draft Model

The operation consumes `DraftStep`, not the core `Step` union. Drafts have a
deliberate authoring vocabulary that is later lowered by
`build_workflow_from_draft`:

- `DraftUseStep`
- `DraftForeachStep`
- `DraftInterruptStep`
- `DraftJoinStep`
- `DraftEndStep`
- `DraftWhenStep`
- `DraftChooseStep`
- `DraftMatchStep`
- `DraftSubgraphStep`

`DraftSubgraphStep` mirrors the declarative boundary fields of
`SubgraphNode`, excluding core-owned `id` and `type`:

```python
class DraftSubgraphPayload(BaseModel):
    workflow: WorkflowRef
    desc: str | None = None
    input_schema: SchemaRef = Field(default_factory=lambda: SchemaRef(type="object"))
    output_schema: SchemaRef = Field(default_factory=lambda: SchemaRef(type="object"))
    input: list[InputBinding] = Field(default_factory=list)
    output: list[OutputBinding] = Field(default_factory=list)
    outcomes: list[str] = Field(default_factory=lambda: ["ok"], min_length=1)


class DraftSubgraphStep(BaseModel):
    subgraph: DraftSubgraphPayload
```

The draft adapter constructs `SubgraphNode` directly from this payload. It
does not load the referenced child artifact; artifact resolution remains a
platform concern.

`DraftInterruptPayload` gains nullable `request_schema` and `resume_schema`
fields. Supplied schemas must be valid JSON object schemas. `None` preserves
the distinction between legacy untyped interrupts and explicit contracts; the
adapter passes only authored schema fields to `WorkflowBuilder.interrupt` so
typed contracts survive draft parsing, validation, artifact creation, and
execution without falsely marking every interrupt typed.

## Application API

Add a generic operation to the workflow API surface:

```python
async def add_step(
    *,
    workspace_id: str,
    revision: int,
    step_id: str,
    step: DraftStep,
    incoming: RouteSource | None = None,
    routes: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Insert one typed draft step and optional route wiring atomically."""
```

`step_id` is separate because draft step identifiers are map keys. The
`DraftStep` payload contains no second identifier that can disagree.

`RouteSource` keeps an incoming edge internally consistent:

```python
@dataclass(frozen=True)
class RouteSource:
    step_id: str
    outcome: str = "ok"
```

For example, `RouteSource(step_id="draft_issues", outcome="ok")` wires
`draft_issues --ok--> <new step>`. RPC supplies the same two-field shape. CLI
commands project `--from-step` and `--from-outcome` into it only after rejecting
`--from-outcome` without `--from-step`.

The operation:

1. receives an already parsed `DraftStep`;
2. rejects an existing `step_id`;
3. checks that `incoming.step_id` exists when supplied;
4. validates supplied top-level route outcomes against the inserted step kind;
5. inserts the canonical `DraftStep.model_dump(mode="json", by_alias=True)`;
6. optionally wires `incoming` to `step_id`;
7. optionally stores outgoing top-level routes; and
8. applies the entire patch through one revision check.

Draft workspaces intentionally permit invalid intermediate graphs. Generic
insertion therefore allows omitted or incomplete outgoing routes. When routes
are supplied, their keys must be a subset of the step's declared outcomes.
`DraftEndStep` and decision steps reject top-level routes because end has no
outgoing edge and `when`/`choose`/`match` embed targets in their own payloads.

Declared top-level outcomes are:

- `use`: capability-declared outcomes when resolvable, otherwise `ok`;
- `foreach`: `loop`, `done`, plus `completed_with_errors` when the item-error
  policy is `skip` or `collect`;
- `interrupt`: `interrupt.outcomes`;
- `join`: `done`;
- `subgraph`: `subgraph.outcomes`.

The capability helper remains distinct because it resolves a capability,
projects schemas, creates bindings, and currently requires complete routes for
multi-outcome capabilities. It may share private insertion mechanics, but its
public behavior must not regress.

Rename the internal `DraftOutcomeRef` value object to `RouteSource` and reuse
it for both generic incoming wiring and existing handle operations. This is a
clean internal migration; no compatibility alias is required.

## JSON-RPC And Python Client

Add:

```text
workflow.draft_workspaces.add_step
```

Its parameter model contains `workspace_id`, `revision`, `step_id`, a typed
`DraftStep`, optional `RouteSourceParams`, and optional routes. Pydantic must
reject malformed or ambiguous step objects before dispatching to the API.

The Python RPC client implements the same method on `WorkflowApi`. Client and
server serialize steps with aliases so fields such as foreach `as` and when
`if` retain their canonical wire names. Round-trip tests cover all nine step
variants, including interrupt schemas and subgraph workflow references.

## CLI Shape

Register a focused Typer application beneath `wf draft`:

```text
wf draft add capability
wf draft add interrupt
wf draft add foreach
wf draft add join
wf draft add end
wf draft add when
wf draft add choose
wf draft add match
wf draft add subgraph
```

The old `wf draft add-step` command is removed. Live docs, tests, skills,
examples, and scripts migrate to `wf draft add capability`.

All commands accept the workspace id, `--revision`, `--step`, and optional
`--from-step`/`--from-outcome`. Commands whose steps use top-level routes also
accept repeatable `--route OUTCOME=TARGET`.

Variant-specific options are:

- `capability`: `--capability`, existing `--input`, and existing
  `--bind-output` flags;
- `interrupt`: `--kind`, optional request/resume schema JSON files,
  repeatable `--request SOURCE=LOCAL_TARGET`, repeatable
  `--resume LOCAL_SOURCE=STATE_TARGET`, and repeatable `--outcome`;
- `foreach`: `--over`, `--as`, `--mode`, `--item-error`, optional
  `--collect-to`, `--max-active`, and `--max-outstanding`;
- `join`: no variant-specific options;
- `end`: `--outcome` and no `--route`;
- `when`: `--condition-file`, `--then`, and `--otherwise`;
- `choose`: `--clauses-file` containing the ordered clause array and
  `--default`;
- `match`: `--value`, `--cases-file` containing the ordered case array, and
  `--default`;
- `subgraph`: exactly one of `--workflow-name` or
  `--artifact-id` plus `--artifact-version`, optional input/output schema JSON
  files, repeatable `--input`, repeatable `--bind-output`, repeatable
  `--outcome`, and optional `--description`.

Structured conditions, clauses, cases, and schemas use JSON files rather than
dense inline JSON. Binding flags retain the existing path conventions. CLI
help gives one valid example per command and tells users to run
`wf draft validate` after editing.

The subgroup belongs in a focused `wf_cli.commands.draft_add` module. Shared
route/binding/JSON-file parsing helpers should move only when both command
modules need them; avoid a broad CLI refactor.

## Validation And Errors

- Pydantic owns draft-step shape validation.
- CLI validates flag relationships and JSON file contents before API dispatch.
- Generic application errors identify duplicate ids, missing incoming source
  steps, unsupported route outcomes, and forbidden top-level routes.
- Revision conflicts preserve existing workspace behavior.
- Failed requests do not mutate the draft or increment its revision.
- No command guesses missing routes, targets, contracts, or bindings.

## Tests

### Draft Model And Adapter

- Typed interrupt schemas parse, dump, and lower to `InterruptNode`.
- Subgraph payloads parse, dump, and lower to `SubgraphNode` without loading an
  artifact.
- Unknown or mixed step-kind keys remain rejected.

### Application

- Parameterized insertion covers every `DraftStep` variant.
- Incoming and outgoing route wiring is atomic.
- Duplicate ids, missing incoming sources, unknown outcomes, and forbidden
  routes fail without mutation.
- Invalid intermediate drafts remain persistable and validate diagnostically.
- Capability insertion preserves existing schema projection and complete-route
  behavior.

### RPC And Client

- Parameter parsing rejects malformed step discriminators and fields.
- App round trips cover every step kind.
- Client payloads use the exact method name and canonical aliases.
- RPC failures occur before draft mutation.

### CLI

- `wf draft add --help` lists all nine commands.
- Per-command help exposes only relevant options.
- Every command builds the expected `DraftStep`, incoming source, and routes.
- Invalid flag combinations fail before calling the API.
- Local and `--target` execution use the same handler method.
- `add capability` preserves existing composed behavior.
- The removed `add-step` command and live references are absent.

## Documentation And Issue Tracking

- Update `docs/wf_cli.md`, `docs/wf_api_architecture.md`, current roadmap
  wording, `skills/wf-cli`, and `skills/wf-workflow` references.
- Update other live references discovered by a fixed-string search; do not
  rewrite historical plans or thesis prose solely to rename an old command.
- Mark all three draft-authoring parity issues resolved when implementation and
  focused verification pass.
- Add newly discovered defects to `ISSUES.md` only when concrete,
  reproducible, and outside this slice. Fix in-scope defects directly.

## Deferred Work

A later parity slice may expose the Python JSON-RPC suite through the
TypeScript Effect RPC package. That slice should start with a machine-checked
method parity manifest. Code generation should be evaluated from the canonical
Python registry and schema export rather than duplicate handwritten
TypeScript definitions.

## Acceptance Criteria

- Every draft step variant can be added through the application API, Python
  JSON-RPC, Python client, and a dedicated CLI command.
- Typed interrupt schemas and subgraph contracts survive draft adaptation.
- One generic `add_step` operation owns raw typed insertion.
- Capability insertion retains its composed projection and binding behavior.
- CLI vocabulary is grouped under `wf draft add` without a ghost alias.
- Invalid requests fail atomically and preserve revision semantics.
- Focused tests, Ruff, basedpyright, and documentation checks pass.
