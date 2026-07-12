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

| Classification | Mode | Route or target | Operator action | Observed result |
|---|---|---|---|---|
| PASS | replay | `/present#scene/thesis/title` | Open the presentation with the replay target selected. | The presentation entry route is reachable without requiring the workflow server. |
| PASS | live health | `/api/health` | Request the web-server health endpoint. | `200` with `{"ok":true,"status":"ok"}`. |
| PASS | live health | `/api/connect` -> `http://127.0.0.1:8765/rpc` | POST the configured RPC target to the web server. | `workflow.health` returned `status: ok`, a store root, and equivalent CLI `uv run wf status`. |
| PASS | live health | `http://127.0.0.1:8765/rpc` | Confirm the target responds through the web server's connection path. | The JSON-RPC request/response exchange was captured successfully. |
| BLOCKED | live end-to-end | Scene 10 -> Scene 12 | Start the prepared run, submit the approval form, and inspect output/trace. | The health path is verified, but this pass did not complete the stateful browser interaction. Do not claim this path was live-verified. |
| BLOCKED | replay end-to-end | Scene 8 -> Scene 12 | Send the prepared request, advance authoring beats, approve/revise, then inspect output/trace. | Route/test and screenshot coverage exists; a complete human-operated browser pass was not captured in this log. |
| PRODUCT | fallback | Scene 10 -> Scene 12 | Point the presentation at an unavailable target and continue. | Fallback behavior is documented and covered by route contracts, but the unavailable-target browser interaction still needs a final manual check. |

### Operator Interpretation

The live connection boundary is working. The evidence above proves that the
presentation-side web server can reach the example workflow RPC server and
decode `workflow.health`; it does not prove that a complete live run,
interrupt/resume branch, output, or trace was completed during this rehearsal.
Use the prepared replay for the defense unless the full stateful live path is
rehearsed separately.

## Follow-up Checks

1. Force replay with the session-storage command in
   [`defense-presentation.md`](defense-presentation.md), then walk the Scene 8
   request through the Scene 12 trace route.
2. With the example server running, start from the Scene 10 footer action and
   record the run ID, approval payload, submitted/revision-requested outcome,
   output, and trace frames.
3. Point the target at an unused loopback port, reload, and record the exact
   fallback badge and available route behavior.
