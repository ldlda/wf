# Typed Workflow Drafts Design

## Goal

Keep `WorkflowDraft` as the LLM-friendly authoring format without letting it
become a second workflow system.

Drafts should:

- have concrete Pydantic models at the authoring seam
- compile into the existing raw/core workflow models
- reuse existing workflow validation rather than reimplementing graph rules
- return structured draft diagnostics without parsing exception strings

## Model Roles

### `WorkflowDraft`

Authoring model.

It owns the intentionally nicer JSON shape:

- `steps` instead of raw `nodes`
- `kind="use"` plus `capability`
- `in` / `out`
- `interrupt_kind`, `request`, `resume`

This model exists because authoring wants a more legible surface than the raw
runtime plan.

### `RawWorkflowPlan`

Low-level transport model for MCP callers that already have a normalized plan.

It reuses core `Step` and `Edge`, but currently keeps boundary schemas as plain
JSON objects. It is not a second workflow language. Converting it into
`Workflow` is nearly a validation/coercion step:

```text
RawWorkflowPlan.model_dump(...) -> Workflow.model_validate(...)
```

### `Workflow`

Core runtime model.

It remains the only normalized graph model consumed by runtime validation and
execution.

## Chosen Design

Add concrete draft models in `wf_artifacts.drafts`:

- `WorkflowDraft`
- discriminated `DraftStep` variants
- `DraftEdge`
- `DraftDiagnostic`

Compilation flow:

```text
dict payload
  -> WorkflowDraft.model_validate(...)
  -> RawWorkflowPlan built from draft models
  -> Workflow.model_validate(...)
  -> existing artifact factory validation on save
```

The compiler only translates the genuine authoring differences. It does not own
workflow graph semantics.

## Error Handling

Use Pydantic error locations and explicit draft errors. Do not infer paths by
parsing exception message text.

Expected diagnostic fields:

- `code`
- `path`
- `step_id` when the failing step is known
- `message`

Patch failures remain their own `patch_invalid` diagnostic.

## Non-Goals

- changing workflow semantics
- changing the raw plan escape hatch
- adding new step kinds
- replacing existing core validation

## Testing

Add tests that prove:

- draft payloads validate into concrete models
- compilation still returns the current raw plan shape
- structured diagnostics identify the failing path and step id
- graph validation remains delegated to the existing normalized workflow path
