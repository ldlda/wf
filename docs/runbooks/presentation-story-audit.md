# Presentation Story-Flow Audit

Audit date: 2026-07-13. This review uses the complete
[rehearsal matrix](presentation-rehearsal-matrix.md), the dated
[rehearsal log](presentation-rehearsal-log.md), the
[presentation runbook](defense-presentation.md), the
[Q&A runbook](defense-qna.md), and the locally available private narrative
notes in `random shit/`. The matrix covers all 14 scenes; the log records
targeted replay/fallback checks and does not establish a completed live
end-to-end run.

## Scene Audit

### Scene 1 — Thesis
- Audience takeaway: The AI-agent goal narrows to an implemented workflow substrate.
- Visible proof: Title and substrate beats state the motivation and the typed lifecycle contribution.
- Missing or confusing: The external-planner boundary must be said before the audience asks where the agent is.
- Next action: keep

### Scene 2 — The Problem
- Audience takeaway: Direct actions do not become reusable automation without durable contracts.
- Visible proof: The contrast and missing-contracts beats name schemas, persistence, traces, and recovery.
- Missing or confusing: The causal bridge from “AI lowers the barrier” to “the platform is still necessary” is spoken, not shown.
- Next action: keep

### Scene 3 — Positioning and Related Systems
- Audience takeaway: lda.chat occupies a typed, provider-neutral substrate position rather than replacing adjacent systems.
- Visible proof: The landscape and lda.chat position map distinguish tool loops, scripts, hosted automation, agent graphs, and MCP.
- Missing or confusing: The comparison can feel like a catalog unless the axis and intended external-agent user are stated once.
- Next action: keep

### Scene 4 — Planner and Runtime
- Audience takeaway: An external planner proposes while the runtime validates, executes, records, and resumes.
- Visible proof: Planner, runtime, and boundary beats make the ownership split visible.
- Missing or confusing: The audience needs the sentence that this is the thesis boundary, not a claim of a new planner.
- Next action: keep

### Scene 5 — Workflow Lifecycle
- Audience takeaway: Draft, Artifact, Deployment, and Run are distinct records with different responsibilities.
- Visible proof: The lifecycle strip shows mutable authoring, immutable artifact, source binding, and persisted execution.
- Missing or confusing: The jump from vocabulary to architecture can be abstract if Deployment is not tied to concrete sources.
- Next action: keep

### Scene 6 — Architecture Zoom
- Audience takeaway: The same public surface reaches API, runtime/providers, stores, and a typed NodeUse execution.
- Visible proof: Client, API, runtime, and NodeUse focus beats provide a semantic zoom with package and operation evidence.
- Missing or confusing: Four nested levels risk becoming a component tour unless each level answers what responsibility moves inward.
- Next action: keep

### Scene 7 — Author, Validate, Repair
- Audience takeaway: Discovery and structured diagnostics reduce agent guessing during workflow authoring.
- Visible proof: Discover, author, diagnose, and repair beats show the operation loop and repair guidance.
- Missing or confusing: The repair result should be verbally connected to the valid artifact, not treated as another isolated tool call.
- Next action: keep

### Scene 8 — Agent Request
- Audience takeaway: A thin external-agent surface can request work without pretending to execute it.
- Visible proof: Send reveals the prepared conversation and four discovery tool calls with no run claim.
- Missing or confusing: The chat surface could be mistaken for the thesis product unless the substrate remains the stated center.
- Next action: keep

### Scene 9 — Prepared Workflow Lifecycle
- Audience takeaway: The request is translated into Discover, Draft, Validate, Artifact, and Deployment stages.
- Visible proof: The phase rail, staged messages, and changing factual evidence advance across all five beats.
- Missing or confusing: Deployment records a local run request but does not execute; that boundary needs an explicit spoken pause.
- Next action: keep

### Scene 10 — Run From Deployment
- Audience takeaway: Execution starts from a ready deployment through a public run operation.
- Visible proof: Input, operation, and graph beats show selected inputs, `workflow.runs.start`, a run ID, and the typed boundary.
- Missing or confusing: The live end-to-end path was blocked, so live output must not be implied from the replay-backed operation view.
- Next action: factual fix

### Scene 11 — Typed Human Boundary
- Audience takeaway: A persisted run pauses at a typed issue-review decision with explicit submitted and revision-requested outcomes.
- Visible proof: Interrupt payload, selected issue, comment field, and both decision controls are visible in replay.
- Missing or confusing: The revision replay uses `run_recorded_lda_report_revision`, so “same run” wording is false for that branch.
- Next action: factual fix

### Scene 12 — Resume, Output, Evidence
- Audience takeaway: A decision leads to inspectable output and trace evidence for the workflow run.
- Visible proof: Resume, output, and trace beats show status, report/issue result, interrupt continuation, and terminal frames.
- Missing or confusing: Submitted replay continuity is demonstrated; live continuity and revision same-run continuity are not yet established.
- Next action: factual fix

### Scene 13 — Evaluation
- Audience takeaway: The 36 trials are bounded engineering evidence about operability and UX failure modes.
- Visible proof: Cohort, validity, and findings beats separate audited evidence from benchmark-style claims.
- Missing or confusing: The evaluation arrives after demo evidence, so the presenter must state that failures motivate the product-surface argument.
- Next action: keep

### Scene 14 — Limits and Conclusion
- Audience takeaway: The contribution is a useful substrate, not a production agent, scheduler, or broad benchmark.
- Visible proof: Limits, future, conclusion, and questions beats distinguish implemented core from future layers.
- Missing or confusing: Q&A must not begin before the contribution sentence and limitations have landed.
- Next action: keep

## Flow Findings

### Transitions

- Scene 1 -> 2 works: the goal becomes the missing reusable-automation contracts.
- Scene 5 -> 6 works if Deployment is the handoff: lifecycle vocabulary becomes the architecture that owns it.
- Scene 7 -> 8 works: authoring/repair operations become a thin external-agent request surface.
- Scene 8 -> 9 works and is not a duplicate: request/discovery becomes staged lifecycle evidence.
- Scene 9 -> 10 is the critical boundary: Deployment prepares; Scene 10 alone starts execution. Keep the explicit no-run wording.
- Scene 10 -> 11 -> 12 works as one climax in replay, but the revision branch has a factual run-identity defect and the live path is blocked.
- Scene 13 -> 14 works: evaluation limits become the contribution and future-work close.

### Order, Duplicated Beats, And Q&A

The 14-scene order is coherent: motivation, positioning, boundary, vocabulary,
architecture, authoring, then demo proof, evaluation, and limits. No duplicated
demo beat was found. Scene 8 introduces the request, Scene 9 owns authoring and
deployment, Scene 10 owns run activation, Scene 11 owns the decision, and Scene
12 owns resume/output/trace. The Q&A branch belongs after Scene 14's Questions
beat; opening a prepared branch earlier would interrupt the argument and make a
discussion answer look like core evidence.

## Defects

- **Factual:** The revision-requested replay has a separate run ID while the
  surrounding same-run wording suggests continuity. Correct the recording or
  label that branch explicitly as a separate prepared recording.
- **Factual:** The live health boundary passed, but live Scene 10 -> 12 was
  blocked. Do not present live output or trace as rehearsed evidence.
- **Visual:** No visual defect was recorded in the available rehearsal log. The
  matrix remains the acceptance checklist for both `1280x720` and `1024x768`.

## Product Follow-ups

These are outside the story-flow acceptance pass and must not be presented as
current proof:

- Add a factual input-file browser that distinguishes declared, selected, read,
  and produced files.
- Complete and record a stateful live run through approval, resume, output, and
  trace.
- Decide whether the revision branch should preserve the submitted run identity
  or remain a separately labeled prepared recording.
- Consider live agent execution, richer trace frames, and real source reads as
  future product layers, not rehearsal fixes.
