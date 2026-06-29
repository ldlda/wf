# Explain Draft Diagnostics Design

## Status

Planned.

## Problem

`wf explain` currently covers deployment/source diagnostics but not the draft
and workflow-core validation codes that agents now hit while authoring
multi-step workflows. The missing explanations force agents to infer behavior
from large schemas, source files, or tests.

The recent challenge runs exposed these recurring failures:

- `unknown_edge_destination`: agents route to a step that does not exist yet,
  for example `--route ok=collect`.
- `invalid_source_path`: agents bind from `input.foo` or `state.foo` before
  that path exists in the draft schema/state.
- `invalid_destination_path`: agents write capability output into undeclared
  state/output paths.
- `draft_invalid` and `patch_invalid`: agents mix raw-plan shape, draft shape,
  and RFC 6902 patch shape.
- `revision_conflict`: iterative draft commands use stale revision numbers.

## Design

Extend the docs-backed explain registry with draft/workflow validation cards.
Where a code already exists in a real enum, use that enum instead of a bare
string:

```python
from wf_core.validation.issues import ValidationIssueCode

ValidationIssueCode.INVALID_SOURCE_PATH.value
ValidationIssueCode.UNKNOWN_EDGE_DESTINATION.value
```

For draft-store codes that are not enum-backed yet, introduce small constants
near the producer before importing them into `wf_cli.explain.entries`.

The registry remains exact-match and docs-backed. It must not become fuzzy
search or command discovery. If a command is unknown, that remains a CLI help
problem unless the CLI emits a stable error code.

## Initial Code Set

Add explain cards for:

- `invalid_source_path`
- `invalid_destination_path`
- `unknown_edge_destination`
- `undeclared_edge_outcome`
- `missing_outcome_edge`
- `unknown_outcome`
- `draft_invalid`
- `patch_invalid`
- `revision_conflict`

## Required Guidance

`unknown_edge_destination` must explicitly mention draft authoring:

```text
In a draft workspace, add the target step first, then route to it with
wf draft handle or wf draft branch. If you are importing a complete graph,
use wf artifact create-from-plan instead.
```

`invalid_destination_path` must mention the focused helper:

```text
For capability output to state, prefer:
wf draft bind WORKSPACE --revision N --step STEP --from local.FIELD --to state.FIELD

For capability output to public workflow output, prefer:
wf draft bind WORKSPACE --revision N --step STEP --from local.FIELD --to output.FIELD
```

`draft_invalid` must distinguish draft shape from raw plan shape:

```text
Use wf schema draft for draft workspaces and wf schema raw for
artifact create-from-plan payloads.
```

## Acceptance Criteria

- `wf explain --list` includes the new draft/workflow codes.
- `wf explain unknown_edge_destination --format markdown` tells agents not to
  forward-route to missing steps in one `add-step` call.
- Explain entries for `ValidationIssueCode` values import the enum, not copied
  string literals.
- Existing explain parser behavior is unchanged.
- Related docs links point to live docs, not `docs/superpowers/**` plans/specs.
