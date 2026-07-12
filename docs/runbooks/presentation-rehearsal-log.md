# Presentation Rehearsal Log

This log records the defense rehearsal gate. It is an operator record, not a
product contract. `PRODUCT` entries are deliberately not fixed as part of the
rehearsal pass.

## 2026-07-13

### Environment

- Viewport: command-line health checks; browser rehearsal matrix remains at
  `1280x720` and `1024x768` from the screenshot runner.
- Web app: `http://127.0.0.1:5173`
- Web server: `http://127.0.0.1:8787`
- Workflow RPC target: `http://127.0.0.1:8765/rpc`
- Example store: `examples/lda_report_workflow/.wf_lda_report_store`

### Checks

| Classification | Viewport | Mode | Route or target | Operator action | Observed result |
|---|---|---|---|---|---|
| PASS | 1280x720 | replay | `/present#scene/agent-handoff/request` | Open the request route and click `Send`. | The prepared conversation appears with the user request, assistant narration, and four discovery tool calls; no run is claimed. |
| PASS | 1280x720, 1024x768 | replay | `/present#scene/typed-human-boundary/approval` | Open the approval route. | The input files, typed interrupt payload, proposed issue, resume comment, `Submit`, and `Request revision` controls are visible. The footer reports `Run paused - review required`. |
| PASS | 1280x720 | replay | `/present#scene/prepared-lifecycle/{discover,draft,validate,artifact,deployment}` | Open each Scene 9 beat directly. | The phase rail advances through Discover, Draft, Validate, Artifact, and Deployment; staged chat groups and factual evidence change with each beat. |
| PASS | 1280x720 | replay | `/present#scene/run-from-deployment/operation` | Open the Scene 10 operation beat. | `workflow.runs.start` is shown as interrupted with deployment, run ID, and `issue_review` boundary; the prepared-workflow action is available in the footer. |
| PASS | 1280x720 | replay | Scene 11 -> Scene 12 | Click `Submit`. | The route changes to `resume`; the output shows `submitted`, `approved: true`, selected issue `risk-1`, and a created issue. |
| FACTUAL | 1280x720 | replay | Scene 11 -> Scene 12 | Reload approval and click `Request revision`. | The route changes to `resume` and shows `cancelled`, `approved: false`, no selected issues, and a revision report. The replay uses `run_recorded_lda_report_revision`, so it does not preserve the submitted branch's run ID despite the same-run wording. |
| PASS | 1280x720, 1024x768 | replay | `/present#scene/resume-output-evidence/trace` | Open the trace beat after the decision branches. | Recorded execution frames render, including `review_issues` interrupt/continuation and `end_cancelled`; the UI exposes the evidence inspector. |
| PASS | 1024x768 | fallback | `/present#scene/typed-human-boundary/approval` | Set the presentation target to `http://127.0.0.1:1/rpc` and reload. | The approval route remains usable with the replay-backed payload and decision form; no live-ready badge is shown. The browser session target was restored afterward. |
| PASS | command line | live health | `/api/health` | Request the web-server health endpoint. | `200` with `{"ok":true,"status":"ok"}`. |
| PASS | command line | live health | `/api/connect` -> `http://127.0.0.1:8765/rpc` | POST the configured RPC target to the web server. | `workflow.health` returned `status: ok`, a store root, and equivalent CLI `uv run wf status`. |
| BLOCKED | 1280x720 | live end-to-end | Scene 10 -> Scene 12 | Start the prepared run, submit the approval form, and inspect output/trace against the live server. | Live health is verified, but a complete stateful live browser path was not completed in this rehearsal. Do not claim live output or trace success. |

### Operator Interpretation

The live connection boundary is working. The evidence above proves that the
presentation-side web server can reach the example workflow RPC server and
decode `workflow.health`; it does not prove that a complete live run,
interrupt/resume branch, output, or trace was completed during this rehearsal.
The replay path is usable at both rehearsal viewports, but its revision branch
currently uses a separate recorded run identity. Use the prepared replay for
the defense unless the full stateful live path is rehearsed separately.

## Follow-up Checks

1. Decide whether the revision branch should preserve the submitted branch's
   run identity or be presented as a separate prepared recording.
2. With the example server running, start from the Scene 10 footer action and
   record the live run ID, approval payload, submitted/revision-requested
   outcome, output, and trace frames.
3. Keep the unavailable-target fallback check in the pre-defense checklist so
   its badge and route behavior can be rechecked after presentation changes.
