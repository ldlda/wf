# Task 1 Implementation Report

## Scope

Implemented the canonical defense rehearsal route manifest and documentation
from `task-1-brief.md`.

- Added `scripts/presentation-rehearsal-routes.json` with all 42 current
  `mainScenes` scene/beat pairs. Each object has exactly `sceneId`, `beatId`,
  `route`, and `fileStem`.
- Added `docs/runbooks/presentation-rehearsal-matrix.md` with one row per route,
  including the presenter sentence, dominant/supporting visuals, chat mode,
  evidence mode, and exact fallback route.
- Linked the matrix from `docs/runbooks/defense-presentation.md` and explicitly
  described it as a rehearsal checklist rather than a new story or product
  contract.
- Extended `storyboard-navigation.test.ts` to validate unique and complete
  bidirectional coverage against `mainScenes`, exact manifest keys, canonical
  route fields, and hash round-trips through `hashForLocation` and
  `locationFromHash`.

## Verification

The test-first check was performed before creating the manifest: the focused
Vitest suite failed with an import-resolution error because
`scripts/presentation-rehearsal-routes.json` did not exist. After adding the
manifest, the same suite passed.

Exact verification commands and results:

```text
pnpm --dir web/apps/console test -- src/presentation/storyboard-navigation.test.ts
PASS: 1 test file, 11 tests

pnpm --dir web/apps/console typecheck
PASS: tsc -b --pretty false

PowerShell JSON validation using ConvertFrom-Json
PASS: manifest entries: 42
PASS: manifest keys: beatId, fileStem, route, sceneId

PowerShell matrix row count
PASS: matrix route rows: 42

git diff --check
PASS: no whitespace errors; Git reported only LF-to-CRLF normalization warnings
```

## Self-Review

- The manifest uses the current `mainScenes` IDs, including `approval`,
  `resume-output-evidence`, and `conclusion/questions`; no historical
  interrupt-evidence or workflow-demo route names were introduced.
- The coverage test fails on a missing beat with its scene ID and rejects stale
  manifest entries, duplicate pairs, incorrect canonical route strings, and
  malformed navigation round-trips.
- Matrix evidence references remain bounded by existing storyboard pointers,
  prepared replay evidence, and the defense runbook fallback wording. No
  expected output was invented.
- All current scene beats use `hidden` chat mode in the storyboard metadata, so
  the matrix records `hidden` consistently rather than inventing full, rail, or
  dock modes.

## Deviations And Concerns

No functional deviations from the brief. The repository emits line-ending
normalization warnings for the touched text files during Git operations; these
are not whitespace errors and do not affect the committed content.

## Commit

Implementation commit: `fce33934` (`docs: define presentation rehearsal route matrix`)
