# Task 6 Report: Build the Discover-Route Capability Playground

## Status

Implemented against baseline `13f56c4c`. The Discover route now composes the
catalog with a Contract/Try capability playground without automatic execution.

## Implementation

- Moved `formatBoundedJson` and its tests from `workspace/authoring` to
  `workspace/domain`, updating all workspace imports.
- Added `CapabilityPlayground` with stable tab and panel names, Contract facts,
  bounded schema disclosures, Add to draft, and a literal-only Try form.
- Added an explicit immediate-execution warning and acknowledgement gate.
- Added wrapper-only deployment input, local serialization/root-object guards,
  in-flight state, rejected-operation alerts, and result receipts.
- Result receipts show outcome, deployment, matching call evidence duration and
  target when available, readable diagnostics, and bounded output. A
  `runtime_error` is presented as completed with an explicit no-run/no-trace
  explanation.
- Integrated the existing capability controller and workspace target/executor
  into Discover while preserving search, inspect, pagination, and draft flows.
- Added responsive playground styling in the existing `global.css` stylesheet;
  this checkout does not contain a separate `workspace.css` file or import.

## TDD Evidence

- RED: `CapabilityPlayground.test.tsx` failed because the component module was
  absent; existing Discover tests remained green.
- GREEN: the component tests passed after the minimal playground implementation.
- GREEN: route-level coverage passed for Contract/Try integration and the inline
  disconnected operation state.

## Verification

```text
pnpm --dir web --filter @lda/console test -- src/workspace/routes/CapabilityPlayground.test.tsx src/workspace/routes/DiscoverRoute.test.tsx src/workspace/domain/format-bounded-json.test.ts
PASS: 3 files, 26 tests

pnpm --dir web --filter @lda/console typecheck
PASS

pnpm --dir web --filter @lda/console build
PASS

git diff --check
PASS
```

React Doctor's package-local command was unavailable. The prescribed fallback
`npx react-doctor@latest --verbose --scope changed` completed with score `98/100`;
its only warning is the pre-existing `StepInputBindingsForm.tsx` giant-component
finding.

The Impeccable detector reported existing `global.css` side-tab and palette
warnings outside the new playground block. New playground white literals were
removed in favor of the existing paper token.

## Concerns

No functional concerns identified. The only non-functional caveats are the
repository's missing `workspace.css` path, the unavailable package-local React
Doctor binary, and the existing detector warning set in `global.css`.
