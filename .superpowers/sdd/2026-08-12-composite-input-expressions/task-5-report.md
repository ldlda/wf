# Task 5 Report: Decode Composite Step Inputs

## Status

Complete. Task 6 was not started.

## Changed Content

- Regenerated `contracts/workflow-api.manifest.json` and
  `web/packages/rpc/src/generated/workflow-contract.ts` using the documented
  generators. The checked contract now carries recursive literal/path/array/
  object expression branches for node-local inputs while workflow outputs stay
  on the simple binding union.
- Added manifest, generated-type, authored-schema, and translator coverage for
  recursive expressions, strict over-specified-variant rejection, and the
  node-local/workflow-output boundary.
- Extended the authored Effect Schema fixtures with a `Schema.suspend`
  recursive decoder. The existing translator now accepts discriminated
  recursive `oneOf` contracts but continues rejecting arbitrary `oneOf` schemas.
- Made RPC CLI projection explicit and exhaustive. Path/value bindings retain
  their inline flags; expression bindings report
  `input_bindings (use --bindings-file)` and are never flattened into a fake
  `--value`.
- Added browser `InputExpression`, `InputExpressionBinding`, and
  `StepInputBinding` types. Authoring clients and controllers now carry the
  complete node-local union, with handwritten recursive copies for paths,
  arrays, objects, and literal values.
- Widened `CapabilityNodeForm` callback types without adding expression editing
  controls. The existing canonical rehydration seam preserves valid expression
  rows instead of classifying them as malformed; editing remains deferred to
  Task 6/7.

## Verification

- `uv run pytest tests/wf_contract_manifest/test_generate.py tests/wf_contract_manifest/test_committed_manifest.py -q`
  — **8 passed**
- `pnpm --dir web --filter @lda/workflow-rpc test` — **142 passed, 6 skipped**
  across 13 files
- `pnpm --dir web --filter @lda/workflow-rpc typecheck` — clean
- `pnpm --dir web --filter @lda/workflow-rpc contract:check` — clean
- Required focused console tests — **54 passed** across 4 files
- `pnpm --dir web --filter @lda/console typecheck` — clean
- `git diff --check` — clean; only expected Windows LF/CRLF warnings were
  reported by Git

## TDD Notes

- Manifest and parity tests were added before the recursive schema and contract
  regeneration; they failed until the new schemas were present.
- The translator test initially failed on the generated discriminated `oneOf`;
  the targeted translator support made it pass while preserving the existing
  arbitrary-`oneOf` rejection tests.
- Browser model, client, controller, form-seam, and canonical rehydration tests
  were added before their corresponding type/copy changes.

## Deviations And Risks

- `canonical-capability-form.ts` and its test were changed even though they were
  omitted from the Task 5 file list. This is the minimal enabling change needed
  for the widened form callback to preserve a valid returned expression and for
  the console typecheck to remain green; no recursive editor or Task 6
  projection was implemented.
- The contract generator emits the node-local union inline in operation params
  rather than a standalone generated `StepInputBinding` alias. Generated type
  tests assert the complete path/value/expression union and the output boundary;
  neither generated artifact was edited manually.
- The legacy form can carry an expression through rehydration and callback
  types, but it still renders/creates only simple path/value controls. The
  recursive editor is intentionally the next task.
