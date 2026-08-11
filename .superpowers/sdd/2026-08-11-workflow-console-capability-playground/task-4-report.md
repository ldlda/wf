# Task 4 Report: Bound and Redact Console Evidence

## Scope

Implemented against baseline `32c99cbe`.

Task 4 adds the pure retention and security boundary for console evidence. It
does not change transport response decoding, Python code, Serena configuration,
or UI styling.

## Implementation

- Added `sanitizeEvidenceValue`, `sanitizeEvidenceRecord`, and `retainEvidence`
  in `web/apps/console/src/workspace/domain/evidence-policy.ts`.
- Redaction is case-insensitive and happens before reading sensitive property
  values. Keys matching authorization, cookie, token, password, secret,
  credential, API-key, or private-key patterns become `[redacted]`.
- The projector is immutable and JSON-safe. It handles cyclic references,
  throwing getters, unsupported values, non-finite numbers, bounded depth,
  bounded strings, and bounded collection entries.
- Sanitized request and response values each receive an independent 32 KiB
  UTF-8 JSON byte budget. The independent budgets preserve request context when
  only the response is oversized. The byte fitter is deterministic and uses
  `[truncated: depth limit]` and `[truncated: evidence limit]` markers.
- Reducer evidence retention now sanitizes the incoming record and keeps only
  the newest 100 records.
- `EvidenceRecord` now requires `target`. Shared read/write executor evidence
  records use `options.target` on success, invocation failure, server failure,
  protocol/decode failure, and operation mismatch. Health, live demo, replay,
  and test fixtures provide target attribution as well.

## TDD Evidence

The initial policy test run failed because the policy module did not exist, and
the new reducer retention assertion observed the old unbounded 101-record
behavior. After the minimal implementation, the policy and reducer tests
passed. A depth test was corrected to use an acyclic deep chain rather than a
cycle, preserving separate coverage for depth and circular-reference markers.

## Verification

- `pnpm --dir web --filter @lda/console test -- src/workspace/domain/evidence-policy.test.ts src/workspace/domain/read-executor.test.ts src/workspace/domain/write-executor.test.ts src/app/state.test.ts`
  - PASS: 4 files, 47 tests
- `pnpm --dir web --filter @lda/console test`
  - PASS: 144 files, 1,223 tests
- `pnpm --dir web --filter @lda/console typecheck`
  - PASS
- `pnpm --dir web --filter @lda/console build`
  - PASS
- `git diff --check`
  - PASS

## Concerns

- The production build reports the pre-existing Vite warning about a minified
  chunk larger than 500 kB; this task did not alter bundling or UI structure.
- Presentation replay evidence uses the explicit target label `replay`, while
  live demo evidence records its connected target.

## Fix Round 1

Review findings addressed:

- Routed presentation replay initialization and live evidence appends through
  the existing `retainEvidence` policy boundary. Initial replay projection now
  sanitizes each record and retains only the newest 100; live appends use the
  same function rather than a second retention implementation.
- Replaced the unanchored redaction regex with exact case-insensitive matching
  for only: `authorization`, `cookie`, `set-cookie`, `token`, `access_token`,
  `refresh_token`, `secret`, `password`, `api_key`, and `api-key`.
- Added coverage for every approved key variant, plus unchanged
  `tokenCount`, `authorizationStatus`, `cookieJar`, and `secretary` keys.
- Added presentation projection coverage for sanitized initial replay evidence
  and newest-100 retention.

Test files changed in this fix round:

- `web/apps/console/src/workspace/domain/evidence-policy.test.ts`
- `web/apps/console/src/presentation/PresentationRoute.test.tsx`

TDD RED command and output:

```text
pnpm --dir web --filter @lda/console test -- src/workspace/domain/evidence-policy.test.ts src/presentation/PresentationRoute.test.tsx
FAIL: 2 failed, 93 passed (95 total)
- ordinary tokenCount was redacted
- projectRecordingToEvidence was not a function
```

Focused GREEN command and output:

```text
pnpm --dir web --filter @lda/console test -- src/workspace/domain/evidence-policy.test.ts src/presentation/PresentationRoute.test.tsx
PASS: 2 files, 95 tests
```

Broader test command and output:

```text
pnpm --dir web --filter @lda/console test
PASS: 144 files, 1,225 tests
```

Typecheck command and output:

```text
pnpm --dir web --filter @lda/console typecheck
PASS: @lda/presentation-sync build; tsc -b --pretty false
```

Diff hygiene:

```text
git diff --check
PASS: exit code 0
```
