# Scene 10 Guided Product Moment Design

## Purpose

Scene 10 should be the strongest product proof in the defense presentation. It
shows that `lda.chat` owns a durable run, pauses at a typed human boundary,
accepts an operator decision, resumes the same run, and leaves inspectable
output/trace evidence.

The current implementation is functionally correct but still reads like several
widgets placed on a slide. The next slice should turn it into a guided product
moment: one dominant visual per beat, immediate readiness on deep links, and
clear transitions from decision to proof.

## Problem

The approval beat currently has three UX problems:

1. **Delayed readiness:** a direct link to
   `#scene/interrupt-evidence/approval` starts replay from the beginning, so the
   approval controls remain disabled until autoplay reaches the interrupt.
2. **Weak hierarchy:** graph, receipt, schema approval, continuity rail, and
   discussion links compete. The viewer must infer which part matters now.
3. **Unclear consequence:** after Submit or Cancel, the UI changes technically,
   but it does not strongly explain what happened to the persisted run.

These are not backend problems. They are presentation-state and composition
problems.

## Design Goal

Make Scene 10 feel like a product flow:

```text
paused persisted run
  -> schema-backed operator decision
  -> same run resumes
  -> output appears outside chat
  -> trace/evidence remains inspectable
```

The presenter should be able to say less because the screen already answers:

- What is waiting?
- What decision is required?
- What happens after Submit?
- Why is Cancel not fake evidence?
- Where is the proof?

## Scope

In scope:

- Scene 10 and immediately related demo timeline projection.
- Replay readiness for direct hashes in Scenes 9 and 10.
- Visual hierarchy for approval/resume/output/trace beats.
- Clear copy for live vs replay proof.
- Tests that pin direct-link readiness and post-decision outcomes.

Out of scope:

- Replacing chat with AI Elements or AI SDK.
- Building a presenter companion.
- Adding a new workflow graph engine.
- Changing Python workflow runtime behavior.
- Adding a new cancelled replay recording.

## Core Interaction

### Direct route readiness

When the route opens a demo beat, replay state should be primed to the minimum
event boundary needed by that beat.

Examples:

- `workflow-demo/operation`: needs `run_start`.
- `workflow-demo/interrupt`: needs `interrupt`.
- `interrupt-evidence/approval`: needs `interrupt`.
- `interrupt-evidence/resume`: needs `run_resume`.
- `interrupt-evidence/output`: needs `completed` or `run_resume` output.
- `interrupt-evidence/trace`: needs `trace_read` or `completed` trace.

This is a presentation projection, not a runtime mutation. Live mode still
executes sequentially when the operator starts the prepared workflow.

### Approval

On the approval beat:

- Submit is enabled immediately when replay has been primed to the interrupt.
- Submit applies the existing submitted replay branch and jumps to `resume`.
- Cancel marks the decision as cancelled and stays on approval.
- Cancel must not display `workflow.runs.resume` in replay.
- The UI should state that replay has no cancelled run evidence.

### Hierarchy

Each beat gets one dominant visual:

- Approval: schema-backed decision surface.
- Resume: operation block for `workflow.runs.resume`.
- Output: result/output panel.
- Trace: trace/evidence receipt.

The graph is context, not the hero, during approval and resume. It may remain as
a compact strip or mini-map, but it must not compete with the decision or
operation proof.

## Components

### Beat Readiness Projection

Add a small model that maps beat IDs to required replay stages.

```ts
export type DemoBeatRequirement = {
  readonly requiredStage: DemoEvent["stage"] | null;
  readonly reason: string;
};
```

This model should live near the existing demo presentation model, not in the
generic timeline reducer. It is presentation-specific.

### Guided Product Moment

Add a presentation component for Scene 10 composition. It can reuse existing
building blocks but owns the hierarchy.

```tsx
<GuidedProductMoment
  beat={beat}
  demo={demo}
  contract={contract}
  operation={operation}
  approvalActions={approvalActions}
  openEvidence={openEvidence}
/>
```

It should avoid nested cards. Use a clear primary region, a slim context region,
and a proof footer/receipt.

### Decision Status Copy

The approval surface should show one of these states:

- Ready: "Run is paused. Submit resumes this same run."
- Submitted: "Submitted. Same run resumed."
- Cancelled: "Cancelled in presentation replay. No resume evidence is shown."

Do not describe replay cancellation as a real persisted cancelled run unless a
live run actually produced that evidence.

## Data Flow

```text
PresentationRoute location
  -> beat readiness requirement
  -> useDemoTimeline primes replay events for that beat
  -> SceneBody/DemoWorkflowScene receives ready demo state
  -> GuidedProductMoment renders the single dominant proof
```

Approval actions stay route-owned:

```text
SchemaApprovalSurface
  -> DemoApprovalActions
  -> PresentationRoute
  -> useDemoTimeline submit/cancel
  -> hash jump or local cancelled state
```

## Testing Requirements

Route tests:

- Direct approval hash renders enabled Submit/Cancel without waiting for
  autoplay.
- Direct resume hash renders `workflow.runs.resume` without waiting for
  autoplay.
- Submit advances to resume and shows resume proof.
- Cancel stays on approval, shows cancelled copy, and does not show resume
  evidence after a delay.

Model tests:

- Beat requirement mapping covers all demo beats.
- Unknown beat returns no requirement.

Component tests:

- Approval beat marks the decision surface as the hero.
- Resume beat marks the operation block as the hero.
- Output/trace beats do not show approval controls.

Visual smoke:

- Capture approval, resume, output, and trace at 1280x720.
- Approval should have one dominant decision surface.
- Resume should have one dominant operation proof.

## Success Criteria

- A direct link to approval is immediately interactive.
- Submit and Cancel consequences are clear without verbal explanation.
- No fake cancelled replay evidence appears.
- Scene 10 reads as one product flow rather than a collection of widgets.
- Existing `/console` behavior is unchanged.
