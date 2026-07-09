# Presentation Lifecycle Story Expansion Design

## Purpose

The defense presentation currently proves run and interrupt behavior, but it
does not give enough screen time to the rest of the thesis contribution. The
result feels dense and narrow: too much run-state detail in one scene, but too
little lifecycle context around draft, artifact, deployment, source bindings,
and evidence ownership.

The next presentation slice should expand the demo climax into more scenes. It
should first show the product lifecycle as durable substrate state, then zoom
into run start, typed interrupt, resume, output, and trace.

## Problem

The current Scenes 9 and 10 try to cover too many jobs:

- agent handoff into a workflow operation
- reusable workflow graph
- prepared deployment
- run input
- interrupt payload
- operator resume form
- resume operation
- output artifacts
- trace frames
- live/replay truth

This creates the wrong hierarchy. The run inspector becomes visually dominant
before the viewer understands what larger lifecycle it belongs to. It also
makes chat feel detached: the chat says "run prepared workflow", while the
screen jumps straight into run evidence instead of showing what already exists
as draft, artifact, deployment, and configured sources.

## Design Goal

Make the product story read as:

```text
External agent or operator request
  -> draft-like authoring surface
  -> saved artifact
  -> deployment with source bindings
  -> run from deployment
  -> typed interrupt
  -> resume payload
  -> output and trace evidence
```

The presentation may still use a prepared replay, but the viewer should see
which parts are durable product state and which part is the active run moment.

## Scene Structure

Replace the current two-scene climax with four product scenes.

### Scene 9: Prepared Workflow Lifecycle

Purpose: show that the prepared report workflow is not just a chat transcript.

Beats:

- `draft`: show authoring/draft intent and focused operations.
- `artifact`: show immutable artifact identity/version.
- `deployment`: show source bindings and drift policy.
- `ready-run`: show the deployment is ready to start a run.

Dominant visual: lifecycle rail with one large factual panel per beat.

### Scene 10: Run Starts From Deployment

Purpose: show the run begins from the deployment and receives workflow input.

Beats:

- `input`: selected documents and issue-board path.
- `operation`: `workflow.runs.start` operation proof.
- `graph`: reusable graph with run id and current node context.

Dominant visual: operation and graph. Chat may narrate, but should not own the
screen.

### Scene 11: Typed Human Boundary

Purpose: show the interrupt as a typed product boundary.

Beats:

- `interrupt`: interrupt payload and resume contract.
- `approval`: operator decision form with large report preview.
- `cancel`: honest replay cancellation state.

Dominant visual: interrupt payload and operator decision. The output panel is
not shown before resume.

### Scene 12: Resume, Output, Evidence

Purpose: show the same run resumes and leaves product evidence.

Beats:

- `resume`: `workflow.runs.resume` operation proof.
- `output`: report and issue-board output.
- `trace`: trace frames and protocol evidence.

Dominant visual: output/report/trace. Evidence receipt remains inspectable.

Existing evaluation and conclusion scenes move after these scenes.

## Data Rules

- Do not invent lifecycle facts. If draft data is not in the recording, label it
  as prepared authoring context and point to `examples/lda_report_workflow`.
- Artifact and deployment facts should be derived from the recorded deployment
  inspect event where possible.
- Run input, interrupt payload, resume payload, output, and trace should be
  derived from the canonical recording or live run state.
- Replay cancellation remains an honest presentation branch. Do not show
  submitted resume evidence after cancel.
- Live/replay truth badge remains visible but should not dominate the story.

## Interaction Rules

- Hash deep links must prime replay state for the scene beat being opened.
- Content panes may scroll internally. The whole presentation viewport must not
  scroll.
- Scrollbars may be visually hidden in presentation mode, but native wheel and
  trackpad scrolling must still work.
- Chat is secondary. It can introduce a scene or run the prepared workflow, but
  it should not crowd graph/evidence scenes.

## Success Criteria

- The viewer can answer where draft, artifact, deployment, run, interrupt, and
  trace fit.
- Scene 11 approval no longer wastes space on pre-resume output.
- Scene 12 output and trace can scroll and remain readable at 1280x720.
- The run story is still factual and replay-backed.
- The route count may grow past 12 scenes; clarity wins over forcing everything
  into the old scene count.

