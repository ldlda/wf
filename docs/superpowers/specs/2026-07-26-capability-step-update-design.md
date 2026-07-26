# Capability Step Update Design

**Status:** Approved design  
**Date:** 2026-07-26

## Summary

Add one revision-checked operation for updating an existing capability-backed
draft step without removing and recreating it or writing raw JSON Patch. The
operation updates step metadata and, when requested, replaces the step's
complete canonical input-binding list in the same atomic revision.

The same slice extends capability-step creation so callers can set metadata and
canonical literal inputs when the step is first added.

## Problem

`DraftUseStep` already supports:

- `desc`;
- `retry`;
- `timeout_seconds`;
- ordered canonical path and literal input bindings.

The focused authoring surfaces do not expose those capabilities coherently.
`wf draft add capability` accepts path inputs through a compatibility map but
cannot set literals or execution metadata. After creation, changing metadata
requires raw JSON Patch or removing and recreating the step. Removing and
recreating is especially poor for agents because it also risks disturbing
routes and output bindings that are unrelated to the intended edit.

The existing `set_step_input_bindings` operation solves canonical input
replacement, but it cannot combine that replacement with metadata changes in
one revision. A focused capability-step update should provide that atomic edit
without becoming a generic step-replacement mechanism.

## Goals

- Update `desc`, `retry`, and `timeout_seconds` on an existing
  `DraftUseStep`.
- Distinguish omitted metadata from explicit clearing.
- Optionally replace the complete ordered canonical input-binding list in the
  same revision.
- Reuse existing capability-aware input validation and schema projection.
- Preserve `use`, output bindings, routes, and all unrelated draft content.
- Expose the operation through Python, JSON-RPC, MCP, and local/remote CLI.
- Let `wf draft add capability` set the same metadata and canonical input
  shapes at creation.
- Preserve stale-revision precedence, exact no-op behavior, and atomic failure.

## Non-Goals

- Changing the step's `use` capability.
- Updating routes or step output bindings.
- Updating non-capability step kinds.
- Replacing the complete `DraftUseStep` document.
- Removing existing compatibility map operations.
- Adding TypeScript RPC coverage in this slice.

Changing `use` is deliberately structural. A different capability can change
input/output schemas and declared outcomes, so callers must remove and add the
step explicitly rather than hiding that migration inside metadata repair.

## Considered Interfaces

### Typed Patch Model

Use one presence-aware `CapabilityStepUpdate` model and pass it through every
transport.

Advantages:

- omission and explicit `null` remain distinct;
- one interface carries the same semantics across Python, RPC, MCP, and CLI;
- validation and mutation remain concentrated in the authoring module;
- future metadata fields can be added without another operation.

This is the selected approach.

### Loose Optional Parameters

Pass one optional parameter per field plus internal sentinel values.

This makes the Python call superficially smaller, but every transport must
reconstruct omission-versus-null semantics. It spreads one concept across
several adapters and is rejected.

### Complete Step Replacement

Require the caller to provide a complete `DraftUseStep`.

This simplifies mutation code but forces callers to preserve `use`, outputs,
and unrelated metadata. It creates avoidable lost-update risk and is rejected.

## Domain Model

The transport-safe update model is:

```python
class CapabilityStepUpdate(BaseModel):
    desc: str | None = Field(default=None, min_length=1)
    retry: int | None = Field(default=None, ge=0)
    timeout_seconds: int | None = Field(default=None, gt=0)
    input: list[InputBinding] | None = None
```

The model's interface includes Pydantic field presence:

| Field state | Meaning |
| --- | --- |
| Field omitted | Preserve the stored value |
| `desc: null` | Remove the description |
| `retry: null` | Remove the retry override |
| `timeout_seconds: null` | Remove the timeout override |
| `input` omitted | Preserve current canonical input bindings |
| `input: []` | Clear canonical input bindings |
| `input: null` | Reject as ambiguous |

An update with no fields set is invalid. The model or operation must reject it
before capability metadata is loaded.

`model_fields_set` is semantic input, not an implementation detail to discard
at a transport seam. RPC and MCP request models therefore carry the update as
a nested object rather than flattening nullable fields into the request
envelope.

## Canonical Authoring Operation

Add:

```python
async def update_capability_step(
    *,
    workspace_id: str,
    revision: int,
    step_id: str,
    update: CapabilityStepUpdate,
) -> dict[str, Any]
```

to `WorkflowDraftAuthoringApi`, the public workflow surface, and `WorkflowApi`.

### Validation And Mutation Order

The operation must:

1. Validate the request envelope, including the non-empty update rule.
2. Load the workspace and check `revision`.
3. Require `steps` to be an object.
4. Require `step_id` to exist.
5. Parse the selected step and require `DraftUseStep`.
6. If `input` is omitted, skip capability resolution entirely.
7. If `input` is present, resolve the unchanged `use` capability and reuse the
   same canonical input preflight used by `set_step_input_bindings`.
8. Build the complete changed step and any projected input/state schemas in
   memory.
9. Return the current workspace summary without a revision increment when the
   resulting step and schemas are exactly unchanged.
10. Apply one JSON Patch containing all changed schema and step fields.

Stale revision must win over missing-step, wrong-step-kind, unavailable
capability, path, overlap, literal, and schema errors. The final
`patch_draft_workspace` call remains the mutation-time race guard.

### Input Replacement

When `input` is present, it replaces the complete ordered input-binding list.
The operation must reuse or extract the semantic implementation behind
`set_step_input_bindings`; it must not maintain a second version of:

- graph source validation;
- local-target overlap detection;
- input/state schema projection;
- literal validation;
- root binding behavior;
- context target handling;
- exact ordering and fan-out preservation.

Clearing input bindings does not delete workflow input/state schema fields
projected by earlier edits. This matches existing canonical replacement
semantics and avoids destructive schema inference.

### Metadata Mutation

Only fields present in `update.model_fields_set` are changed. Explicit `null`
removes the corresponding optional field from the canonical step, which is
dumped with optional `None` fields excluded. Omitted fields retain their parsed
values.

`retry=0` is valid. `retry<0`, `timeout_seconds<=0`, and an explicitly supplied
empty description fail request-model validation.

## Capability-Step Creation Parity

Extend `add_step_from_capability` with:

- `desc`;
- `retry`;
- `timeout_seconds`;
- canonical `input_bindings`.

The existing `input_map` remains a compatibility adapter for real callers.
Supplying both `input_map` and `input_bindings` is invalid. Canonical callers
and new transports should use `input_bindings`.

Creation uses the same binding preflight and schema projection as update and
`set_step_input_bindings`. It persists the metadata directly on the new
`DraftUseStep`, so a caller that already knows these fields does not need a
second revision.

The operation's route and output-binding behavior remains unchanged.

## JSON-RPC

Add:

```text
workflow.draft_workspaces.update_capability_step
```

with parameters:

```json
{
  "workspace_id": "report",
  "revision": 4,
  "step_id": "publish",
  "update": {
    "desc": "Publish the report",
    "retry": 2,
    "timeout_seconds": 30,
    "input": [
      {
        "path": "state.report.title",
        "target": "request.title"
      },
      {
        "value": "markdown",
        "target": "request.format"
      }
    ]
  }
}
```

The client must preserve omitted fields and exact input-binding order. It
serializes the nested update with `exclude_unset=True`; otherwise default
`None` values would become unintended clear operations. The existing
`add_step_from_capability` request gains optional metadata and canonical
`input_bindings`; its compatibility `input_map` remains accepted but cannot be
combined with the canonical field.

## MCP

Add:

```text
wf.workflow.update_capability_step
```

with a typed request carrying `workspace_id`, `revision`, `step_id`, and nested
`update`.

The tool delegates once to `WorkflowApi.update_capability_step`. Its
description must state that:

- `use`, routes, and outputs are preserved;
- omitted fields are preserved;
- explicit metadata `null` clears;
- supplied `input` replaces the complete canonical list.

The tool belongs in the stable workflow search allow-list. Extend the existing
capability-add request with the creation-parity fields.

## CLI

Add a dedicated update group in a focused module:

```text
wf draft update capability
```

Example:

```bash
wf draft update capability report \
  --revision 4 \
  --step publish \
  --description "Publish the report" \
  --retry 2 \
  --timeout-seconds 30 \
  --input state.report.title=request.title \
  --value request.format='"markdown"'
```

Clearing:

```bash
wf draft update capability report \
  --revision 5 \
  --step publish \
  --clear-description \
  --clear-retry \
  --clear-timeout \
  --clear-input
```

### CLI Rules

- `--description` and `--clear-description` are mutually exclusive.
- `--retry` and `--clear-retry` are mutually exclusive.
- `--timeout-seconds` and `--clear-timeout` are mutually exclusive.
- `--bindings-file` is mutually exclusive with `--input`, `--value`, and
  `--clear-input`.
- `--clear-input` is mutually exclusive with `--input` and `--value`.
- At least one update field or input mode is required.
- All mode errors occur before CLI context loading.
- `--input` means `GRAPH_SOURCE=LOCAL_TARGET` and is repeatable.
- `--value` means `LOCAL_TARGET=JSON` and is repeatable.
- Convenience flags serialize path bindings first and literal bindings second,
  matching `set-input`.
- `--bindings-file` is the lossless path/value interleaving form.

Extend `wf draft add capability` with:

- `--description`;
- `--retry`;
- `--timeout-seconds`;
- `--value`;
- `--bindings-file`.

Its existing `--input` flag remains the path-binding convenience form.
`--bindings-file` is mutually exclusive with `--input` and `--value`.

The update and add commands must reuse the existing canonical input flag/file
parsers. They must not add a third parser for the same binding union.

## Error Contract

After request-envelope validation, focused errors include:

- workspace or step not found;
- stale revision conflict;
- selected step is not capability-backed;
- empty update;
- explicit `input: null`;
- capability unavailable when input replacement needs its schema;
- undeclared graph source;
- overlapping local targets;
- literal target absent from the capability input schema;
- incompatible source/target schema;
- invalid metadata constraints.

All semantic errors leave the complete workspace unchanged.

Metadata-only updates succeed even when the capability source is currently
unavailable because they do not require capability schema inspection.

## Testing

### Authoring

- Preserve omitted fields.
- Set and explicitly clear each metadata field.
- Accept `retry=0`.
- Reject invalid metadata constraints.
- Replace, clear, and exactly no-op canonical input.
- Apply metadata and input replacement in one revision.
- Preserve `use`, output bindings, and routes.
- Skip capability resolution for metadata-only changes.
- Validate capability-aware paths, literals, roots, overlaps, and schemas by
  the shared input-binding implementation.
- Prove stale revision wins over every semantic error.
- Prove all failures leave the workspace unchanged.
- Compile and run a draft after a combined path/literal update.

### Creation

- Persist metadata at creation.
- Preserve ordered path/literal bindings.
- Accept a lossless bindings file through CLI.
- Reject simultaneous compatibility and canonical input forms.
- Preserve existing route and output behavior.

### Transports

- JSON-RPC model preserves omitted fields versus explicit `null`.
- JSON-RPC client preserves exact canonical input order.
- MCP request validation rejects malformed updates.
- Real MCP tool invocation delegates typed update data once.
- Local and remote CLI produce equivalent operation payloads.

### CLI

- Pin every set/clear exclusivity rule.
- Pin bindings-file exclusivity.
- Reject empty update before loading context.
- Verify add and update help text.
- Verify explicit metadata clears serialize as present `null`.

## Documentation

Update:

- `ISSUES.md`;
- `docs/wf_cli.md`;
- `docs/workflow_drafts.md`;
- `docs/workflow_capabilities.md`;
- `docs/wf_mcp_operator_manual.md`;
- `skills/wf-cli/SKILL.md`;
- `skills/wf-workflow` draft/lifecycle references;
- `docs/current_roadmap.md`.

Document that capability update is a focused patch, not capability replacement,
and that output bindings/routes remain separate operations.

## Success Criteria

- One atomic operation updates capability-step metadata and optional canonical
  inputs without changing `use`, outputs, or routes.
- Omission, explicit clearing, replacement, and no-op semantics are verified.
- Creation can set the same metadata and canonical literal inputs directly.
- Python, JSON-RPC, MCP, and local/remote CLI expose the same behavior.
- Existing compatibility callers remain functional.
- Focused tests, Ruff, formatting, and basedpyright pass.
