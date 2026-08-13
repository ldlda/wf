# Task 5 Second Repair Report

## Status

Complete. Task 6 was not started.

## Fixed Findings

### P1: Context-aware runtime expression budget

Removed the global expression-shape scan from runtime validation. The new
`hasBoundedInputExpressionsAtSchema` helper follows the generated operation
payload or success schema and only invokes the canonical 1024-node expression
counter at `StepInputBinding` and `InputExpressionBinding` positions.

Generic JSON components such as `JsonObject` are no longer interpreted by
their keys. This preserves ordinary values shaped like
`{ kind: "literal", value: ... }` in both simple `InputValueBinding.value` and
`workflow.runs.start.workflow_input`, while genuine over-budget expressions
remain rejected. Authored fixture validation continues to use the recursive
expression schema and the same node budget.

Added adversarial runtime regressions for both accepted ordinary-value cases;
the existing actual-expression and nested-literal rejection tests remain
green.

### P2: Lossless legacy binding order

Replaced the legacy form's simple-row-plus-expression suffix construction with
a stable merge. Existing expression rows stay at their original positions.
Existing simple rows claim a matching original kind/target slot first, fall
back to the next unused row of the same kind when an edit changes its target,
and unmatched serialized rows are appended as genuinely new rows.

Added interaction regressions for no-op `[expression, path]` and mixed
`[path, expression, value]` sequences. Both now submit in their original
canonical order without duplicating expression rows.

## TDD Evidence

The new runtime and form interaction tests were added before the production
changes. The initial focused runs reproduced both rereview failures; the final
focused runs are green.

## Verification

- Python Task 5 focused suite — **168 passed**
- `pnpm --dir web test` — **1,652 passed, 6 skipped** across RPC,
  presentation-sync, console, and server workspaces
- RPC `contract:check` — clean
- RPC typecheck — clean
- Console typecheck/build — clean; existing Vite chunk-size warning only
- Focused runtime-schema and CapabilityNodeForm tests — **25 passed**
- `git diff --check` — clean; only expected Windows LF/CRLF warnings

No generated contract files were modified, Serena configuration was untouched,
and Task 6 was not started.
