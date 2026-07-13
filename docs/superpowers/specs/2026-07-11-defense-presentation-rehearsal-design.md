# Defense Presentation Rehearsal Design

## Status

Proposed implementation slice for the operational path of the React defense
presentation.

## Purpose

The presentation must be rehearsable as a deterministic defense artifact. The
presenter needs one documented live path, one documented replay path, and clear
expected evidence for both submitted and revision-requested decisions.

## Scope

This slice hardens documentation and repeatable verification. It does not add a
real LLM, a remote presenter companion, a new workflow server transport, or new
presentation story content.

## Live Path

With `wf-rpc-server` running against `examples/lda_report_workflow/wf.config.json`
and the presentation target set to `http://127.0.0.1:8765/rpc`, the rehearsal
path is:

1. Open Scene 7 at `#scene/agent-handoff/request`.
2. Use the visible `Run prepared workflow` action.
3. Advance through the prepared lifecycle and run scenes to the typed approval.
4. Choose all issue rows or a deliberate subset, add a comment, and submit.
5. Confirm the same run continues into output and trace proof.

The expected submitted branch has a completed run, generated report output,
created issues for the chosen rows, and trace frames for the completed path.

## Revision-Requested Path

`Request revision` is a valid resume decision, not a terminal cancellation. It
must call `workflow.runs.resume` on the same run with `approved: false`, then
continue to its negative output and trace branch. Its expected evidence is:

- protocol outcome `cancelled`;
- presentation wording `Revision requested`;
- no created issues;
- output headed `Revision Requested`;
- trace records that include `revision_requested` and `end_cancelled`.

## Replay And Failure Path

The committed replay remains the fallback when the health probe or live RPC
operation fails. The runbook must state how to choose replay before a defense,
how to recognize the replay truth badge, and that no time should be spent
debugging a port during the defense.

## Verification Contract

Automated route-level coverage must exercise:

- live target readiness and visible start affordance;
- a submitted approval that advances to same-run output/trace;
- a revision-requested approval that also advances to same-run negative
  output/trace;
- replay fallback when the target fails health checking.

The runbook must add an operator checklist that names the exact startup
commands, deep links, expected screen states, reset procedure, and fallback
statement.

## Acceptance Criteria

1. A new operator can rehearse both decision branches without reconstructing
   the intended state from source code.
2. Documentation distinguishes the product-visible revision request from the
   protocol-level `cancelled` outcome.
3. Browser-level or route-level tests guard both branches and replay fallback.
4. The live path remains optional; a failed target cannot block a replay-based
   defense.
