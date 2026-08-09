# Task 2 Report

## Outcome

Task 2 is implemented on `main`. The console now has a pure selected-step
projection for keyed and compiled drafts, parser-first canonical input/output
binding handling, unsupported-row preservation, ordered row serializers,
schema-informed suggestions and source previews, structural diagnostic mapping,
and presence-aware setup metadata projection.

## Changed Files

- `web/apps/console/src/workspace/domain/draft-workspace-models.ts`: Added `StatePath`, `OutputBinding`, and focused input/output binding mutation input types.
- `web/apps/console/src/workspace/authoring/selected-step-dataflow.ts`: Added canonical projection, structural path guards, row projections, single-row and list serializers, schema helpers, preview selection, and diagnostic ownership mapping.
- `web/apps/console/src/workspace/authoring/selected-step-dataflow.test.ts`: Added keyed/compiled equivalence, ordering, null/zero/absent metadata, structural paths, malformed rows, output target rejection, serializer save blocking, suggestions, previews, and positive/negative diagnostic tests.
- `web/apps/console/src/workspace/authoring/canonical-capability-form.ts`: Preserved absent setup metadata as omitted properties without synthesizing nulls in the binding projection.
- `web/apps/console/src/workspace/authoring/canonical-capability-form.test.ts`: Added absent, explicit-null, and numeric-zero metadata tests.
- `.superpowers/sdd/2026-08-09-workflow-console-selected-step-dataflow/task-2-report.md`: This report.

## TDD Evidence

### RED

After writing the pure projection and setup tests, the prescribed command failed
before collecting tests because `selected-step-dataflow.ts` did not exist:

```text
Test Files  1 failed (1)
Tests       no tests
Error: Failed to resolve import "./selected-step-dataflow.js"
```

This was the expected missing-production-module failure from the Task 2 brief,
not a test assertion or environment failure.

### GREEN

The first implementation run exposed five behavior/type defects. They were
fixed test-first: structural state path segments were preserved, structural
input roots were included during serialization, missing previews returned
`null`, focused diagnostics honored the requested field, and array-item target
suggestions were asserted. The final focused run passed:

```text
Test Files  2 passed (2)
Tests       10 passed (10)
```

## Verification

- `pnpm --dir web --filter @lda/console test -- src/workspace/authoring/selected-step-dataflow.test.ts src/workspace/authoring/canonical-capability-form.test.ts`: passed, `10/10`.
- `pnpm --dir web --filter @lda/console test -- src/workspace/authoring/selected-step-dataflow.test.ts src/workspace/authoring/canonical-capability-form.test.ts src/workspace/authoring/ContextInspector.test.tsx src/workspace/authoring/CapabilityNodeForm.test.tsx`: passed, `17/17`.
- `pnpm --dir web --filter @lda/console typecheck`: passed.
- `git diff --check`: passed; Git reported only normal LF/CRLF conversion warnings for modified files.
- No Serena configuration was modified.

## Deviations

- No controller, transport, or React dataflow forms were added. Those are later
  plan tasks; Task 2's exact file list is limited to the domain models, pure
  projection module/tests, and canonical setup projection/tests.
- The compiled fixture uses the repository's actual `nodes[]` capability key,
  `node`, while keyed drafts use `use`.
- The list serializers return `null` while unsupported rows remain, providing the
  pure save-blocking behavior needed by later forms; removing unsupported rows
  before serialization is the explicit repair path.

## Concerns

- `bindingDiagnosticsForStep` receives only diagnostics, `stepId`, and field, so
  it conservatively anchors `nodes[N]` ownership to the first matching selected
  step node diagnostic. If a backend sends a node-indexed diagnostic without a
  matching `step_id` or without another selected-step node anchor, it remains
  unmatched rather than risking assignment to the wrong row. The keyed JSON
  Pointer and focused `bindings[M]` forms do not have this limitation.
- Literal input values remain typed as the existing domain `unknown`; the
  generated RPC/runtime contract remains authoritative for recursive JSON-value
  validation at transport time.
