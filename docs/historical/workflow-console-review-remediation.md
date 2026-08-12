# Workflow Console Review Remediation

Historical record of the completed triage for the CodeRabbit review captured
in `random shit/rabbitreview/vvvv.txt`. Findings were verified against the
product contracts rather than applied mechanically.

## Completed Repairs

- Repaired auto-applied CSS lookup, shell quoting, and failed-submit behavior.
- Serialized draft reloads and mutations and isolated stale workspace,
  connection, and selection responses.
- Preserved exact conflict-reapply intent and returned the canonical draft with
  revision conflicts.
- Normalized nullable Pydantic schemas into typed controls and stopped repeated
  capability-pagination cursors.
- Preserved valid `oneOf` exclusivity during runtime-contract generation and
  compared parity against the exported RPC schemas.
- Preserved ordered mixed input bindings and unsupported raw rows for explicit
  repair.
- Aligned create/edit timeout fields with the positive-integer API contract.
- Added standard Arrow, Home, and End behavior to inspector tabs.
- Isolated schema-form IDs and radio groups, reset state on schema replacement,
  and retained stable array-row control identity after removals.
- Rejected negative and sparse array projection targets and canonicalized
  diagnostic identities recursively.
- Added an explicit `WEB_TRUSTED_ORIGINS` allowlist for TLS-terminating proxies
  without trusting forwarded headers.

## Contract Correction

The review proposed requiring a nonempty `parts` array for every structural
binding path. That is not the canonical model: node-local `.` and whole graph
sources are valid root paths. The final parity contract permits empty local and
readable graph paths while continuing to reject a root-only writable state
path.

## Deferred Findings

Formatter-only churn, speculative memoization, bounded-serialization
performance changes, and unreachable null-item UI handling were not retained.
Persistent product gaps remain tracked in [`ISSUES.md`](../../ISSUES.md), not in
this historical remediation checklist.
