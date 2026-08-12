# Workflow Console Review Remediation

This is the active triage for the CodeRabbit review captured in
`random shit/rabbitreview/vvvv.txt`. Findings are grouped by verified product
impact rather than the reviewer's severity labels. Do not implement the whole
review mechanically: the report contains invalid findings, low-value refactors,
and auto-applied edits that currently break tests or failure behavior.

## Immediate Repair Gate

Repair the current auto-applied working tree before starting composite input
expressions:

1. Replace the incompatible `fileURLToPath(import.meta.url)` CSS test lookup.
2. Keep the corrected POSIX shell quoting and update its stale RPC expectation.
3. Clear input rows only after `onSubmit([])` succeeds; preserve rows on failure.

## Completed In The Current Working Tree

- Repaired the incompatible CSS test lookup, stale shell-quoting expectation,
  and premature input-row clearing introduced by auto-apply.
- Draft reloads and mutations now share one pending-request guard in both
  directions; duplicate reloads can reuse the same request.
- Remembered capability forms are reactive state while the exact conflict
  reapply payload remains stored independently.
- Capability add reapply preserves the original connector insertion context;
  capability update reapply preserves the original step target.
- Responses for a no-longer-selected step remain isolated without reporting a
  false workspace mismatch or resetting the new inspector.
- Responses from an obsolete workspace or connection provenance cannot mutate
  the current authoring state, including the stale-selection path.
- Revision-conflict responses now include the current canonical draft for
  refresh and rebase.
- Nullable Pydantic `anyOf: [T, null]` fields normalize into typed controls
  while retaining their title, description, and default metadata.
- Automatic capability pagination stops when a server repeats its cursor.
- Every structural authored binding path requires at least one path segment.
- Runtime generation rewrites `oneOf` only when distinct JSON branch types
  prove that exclusivity is preserved; overlapping branches remain `oneOf`.
- Correct POSIX apostrophe escaping remains covered by an RPC regression test.

## Should Fix

- Preserve mixed literal/path binding order and raw JSON intent.
- Align create/edit timeout validation with the positive-integer API contract.
- Add Arrow, Home, and End keyboard behavior to roving inspector tabs.
- Give each schema form unique control IDs and radio names.
- Reset schema-form state deliberately when its schema changes and use stable
  array-row identities.
- Reject negative array indices and canonicalize diagnostic identity.
- Compare parity against exported runtime RPC schemas, not only fixtures.
- Add explicit trusted-origin configuration for deployments behind TLS
  termination; do not trust forwarded headers implicitly.

## Auto-Applied Disposition

Keep after focused tests: direct disabled-button selection, viewport height
clamping, stale receipt flushing, unknown capability kind, draft lifecycle-token
ordering, bounded JSON recursion, evidence credential redaction, runtime-error
icon, trimmed capability query, computed schema-source reuse, and POSIX shell
quoting.

Revise before keeping: the CSS test path lookup and input-row clear behavior.
Remove formatter-only churn where it obscures the substantive change.

Reject or defer: unreachable null-item Add-button handling, removal of complete
catalog loading without replacement pagination UI, bounded evidence
serialization performance speculation, and broad memoization/deduplication/
formatting nits.

## Execution Order

1. Restore the focused test suites and safe failure behavior.
2. Fix authoring concurrency, conflict recovery, and canonical data fidelity.
3. Fix schema normalization and generated/runtime contract parity.
4. Fix form accessibility and reliability.
5. Address proxy/origin and route-boundary hardening.
6. Batch only the test nits and refactors that remain worthwhile.
