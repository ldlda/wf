# Draft Invalid Intermediate Authoring Design

## Status

Planned.

## Problem

Draft workspaces are supposed to support iterative authoring, but some semantic
helpers behave too much like final validation gates. In challenge runs, agents
tried:

```powershell
wf draft add-step browser_click `
  --revision 1 `
  --step wait `
  --capability local.browser_click.wait_for_click `
  --from-step call `
  --route ok=collect
```

The intent is reasonable: add `wait`, route it to `collect`, then add `collect`.
Today this can fail the whole command because the route points at a missing
step. The agent loses the useful partial edit and has to rediscover the order:
add steps first, then route later.

## Design

Draft workspace mutation should persist structurally patchable intermediate
states even when validation reports draft-level errors. The workspace may become
`status: "invalid"` with diagnostics, but the revision should still advance when
the patch itself was valid and the resulting document can still be stored.

Strictness remains at boundaries:

- `wf draft save` must reject invalid drafts.
- `wf draft compile` must reject invalid drafts.
- `wf artifact create-from-plan` remains strict for raw plans.
- malformed JSON Patch remains non-mutating and does not burn a revision.

This is a draft authoring behavior change, not a runtime behavior change.

## First Target

The first target is forward routes:

```text
routes.<step>.<outcome> = "missing_step"
```

Expected behavior:

- The edit is stored.
- The workspace revision increments.
- The workspace status becomes `invalid`.
- Diagnostics include `unknown_edge_destination`.
- The user can add the missing step in a later revision.
- `wf draft validate` becomes valid after all missing route destinations exist.

## Non-Goals

- Do not allow invalid drafts to be saved as artifacts.
- Do not hide diagnostics or downgrade errors to success.
- Do not add a `wf draft step ...` namespace in this slice.
- Do not make `wf explain` fuzzy or command-discovery oriented.

## Acceptance Criteria

- A focused test proves `wf draft add-step --route ok=collect` persists an
  invalid workspace when `collect` does not exist yet.
- A follow-up edit that adds `collect` can make the same workspace valid.
- `wf draft save` and `wf draft compile` continue to reject the invalid
  intermediate workspace before the missing step is added.
- Diagnostics remain machine-readable and include the original code.
- Docs/skills explain the intended sequence: add step, route with
  `wf draft handle` / `wf draft branch`, validate, then save.
