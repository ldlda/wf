# Presentation Evaluation And Closing Design

## Purpose

Scenes 12 and 13 close the defense with evidence, claim boundaries, and a clear
statement of the thesis contribution. They must not read as a model leaderboard
or as a generic list of limitations. The ending should move from bounded
evaluation evidence, through supported future work, back to the stable
planner/runtime boundary, and finally into examiner questions.

This design replaces the current three-number evaluation row and generic
conclusion narrative with two dedicated presentation scenes.

## Design Principles

- Treat the 36-trial campaign as bounded longitudinal engineering evidence,
  not a controlled model comparison.
- Prefer one continuous visual artifact per scene over a collection of cards.
- Preserve exact thesis counts and non-claims.
- Keep chat hidden. The final scenes belong to the thesis argument and its
  evidence, not to the prepared demo agent.
- Reuse the editorial canvas, stage caption, discussion panel, evidence text,
  and existing presentation tokens.
- Keep all primary content readable at 1280 by 720 and 1024 by 768, including
  browser zoom with internal stage scrolling where necessary.
- Use motion only to shift emphasis or reveal a new evidence layer. Reduced
  motion must preserve the complete meaning.

## Scene 13: Evaluation Evidence Board

Scene 13 uses one persistent evaluation board. Each beat changes emphasis
inside the same board so the audience does not have to reconstruct the campaign
from unrelated layouts.

### Beat: `cohort`

The cohort equation is the dominant artifact:

```text
2 challenges x 2 hosted models x 3 instruction profiles x n=3 = 36 trials
```

An audited outcome rail beneath the equation shows the exact counts:

- 27 clean product-path passes
- 8 invalid evaluation samples
- 1 failure

The interface must say `audited outcomes`, not `success rate`. It must not show
percentages or rank models or profiles.

### Beat: `validity`

The cohort equation remains visible as context but recedes. The dominant visual
becomes an audit reconciliation:

```text
automatic result                 manual evidence audit
7 automatic successes    ->      invalid as clean evidence
3 automatic failures     ->      accepted from saved evidence
```

The board states the claim boundary verbatim:

> Bounded longitudinal engineering evidence, not a controlled model
> comparison.

Supporting copy explains that manual audit separates task completion from
valid product-surface evidence. It must not imply that automatic grading is
generally unreliable; the claim is limited to this campaign.

### Beat: `findings`

The board resolves into observed engineering findings. Use a connected ledger
or annotated rail, not six generic cards. Display these findings:

1. Schema discovery
2. Repair hints
3. Binding commands
4. Output schemas
5. Shell assumptions
6. Source contamination

The framing is `UX gaps exposed by trials`. The scene may say that individual
trials revealed these gaps. It must not claim statistical significance,
controlled profile effects, token savings, model superiority, or general model
performance.

### Evidence And Discussion

The scene keeps the existing evidence pointer to the thesis Evaluation and
Appendix C. The existing `evaluation-validity` discussion branch remains
available from the scene discussion rail.

## Scene 13: Boundary, Future Layers, And Questions

Scene 13 uses a stable contribution line as its central visual:

```text
External planner -> typed workflow substrate -> deterministic runtime
                            |
                            v
                  persisted, inspectable evidence
```

The substrate remains in the center across all beats. Surrounding content may
appear or recede, but the center must not move enough to make the audience
relearn the diagram.

### Beat: `limits`

The contribution line dominates. Three explicit non-claims appear below it:

- Not a production sandbox
- Not a scheduler
- Not a broad agent benchmark

The copy must not imply that these are partially delivered features.

### Beat: `future`

Five supported future-work branches appear around the stable substrate:

1. External agent interface and planner loop
2. Production security and credentials
3. Scheduling and hosted operations
4. Stronger controlled evaluation
5. Runtime and provider expansion

Each branch uses a short label and one concrete example. The branches are
surrounding layers, not requirements that belong inside the deterministic core.
The visual must preserve the planner/runtime boundary.

### Beat: `conclusion`

The future branches recede. The stable contribution line becomes the only
dominant artifact. The closing statement is:

> Planner proposes; runtime executes.

Supporting copy may state that the typed workflow substrate makes reusable
agent-operated automation inspectable. It must not describe the submitted
prototype as a bundled autonomous agent.

### Beat: `questions`

Arrow Right from the conclusion enters a full-stage defense discussion index.
This is the transition from the prepared talk to examiner questions.

The index gathers every existing discussion branch and groups it by defense
topic:

1. Thesis contribution
2. Positioning and related systems
3. Runtime and lifecycle
4. Authoring and validation
5. Demo integrity
6. Evaluation
7. Production readiness and future work

Each entry uses the branch's existing title and opens the existing
`DiscussionPanel`. Closing a discussion returns to the Questions beat, not to
the branch's original parent scene. The index must derive its entries from the
canonical discussion-branch catalog; it must not duplicate branch titles or
answers in a second data structure.

The Questions beat is a reusable presentation component but is only exposed as
the final Scene 13 beat in this slice. A future presenter shortcut may open it
globally without changing the component.

## Component Boundaries

### `EvaluationEvidenceScene`

Owns the evaluation-board composition and beat-specific emphasis. Its facts
come from a small typed presentation model colocated with the scene rather than
being embedded across JSX and CSS selectors.

### `ConclusionScene`

Owns the stable contribution diagram, non-claim strip, future-work branches,
and beat-specific emphasis. It does not own discussion navigation.

### `DefenseDiscussionIndex`

Receives the canonical discussion branch definitions and an `openDiscussion`
callback. It groups branches through an explicit branch-to-topic projection.
The projection must be exhaustive so a newly added discussion branch cannot
silently disappear from the index.

### `SceneBody`

Routes the `evaluation` and `conclusion` views to their dedicated components.
It passes `openDiscussion` to the discussion index. It should not gain the new
scene-specific rendering logic itself.

## Interaction And Motion

- Arrow Left and Arrow Right continue to navigate beats through the existing
  presentation reducer and hash routes.
- Selecting a discussion index entry uses the existing discussion route and
  panel.
- Escape closes the discussion panel and returns to the Questions beat.
- Cohort, validity, and findings transitions may fade or shift emphasis over
  150 to 250 milliseconds.
- Future branches may reveal progressively, then recede for the conclusion.
- Motion-disabled and `prefers-reduced-motion` states show the final layout
  without transitional transforms.
- No autoplay is required for these scenes.

## Accessibility

- The evaluation board has a labelled group and semantic lists for outcomes
  and findings.
- Counts and categories remain understandable without color.
- The contribution line and future branches use text labels in addition to
  connector styling.
- The discussion index is a labelled navigation region containing standard
  buttons or links with visible focus treatment.
- The active beat changes visual emphasis but never removes the factual context
  required to understand the scene.

## Responsive Behavior

- At wide canvas sizes, the evaluation equation and audit reconciliation may
  use horizontal flow.
- At narrower 4:3 canvas sizes, the equation wraps into two rows and the audit
  reconciliation stacks without changing reading order.
- The future-work map may tighten around the substrate at 4:3 but must not
  overlap connectors or discussion controls.
- The discussion index uses two columns when space permits and one internally
  scrollable column when browser zoom or canvas width requires it.
- Scrollbars may be visually quiet, but all content must remain reachable by
  wheel, touchpad, and keyboard.

## Testing And Verification

Implementation follows test-driven development.

Automated coverage must include:

- exact Scene 12 cohort and outcome counts;
- absence of percentages and model-ranking language;
- validity reconciliation counts and claim-boundary wording;
- all six observed UX findings;
- all three Scene 13 non-claims;
- all five supported future-work branches;
- stable closing contribution wording;
- the fourth `questions` beat and direct hash route;
- exhaustive inclusion of every canonical discussion branch in the index;
- discussion open and close returning to the Questions beat;
- semantic labels for the evaluation board, contribution diagram, and
  discussion index;
- responsive class or data-attribute contracts used by the CSS composition.

Verification includes focused presentation tests, the full console
presentation suite, console typecheck, production build, and Playwright
screenshots at 1280 by 720 and 1024 by 768 for every new beat. Browser review
must check clipping, reading order, projector contrast, and the transition from
conclusion into Questions.

## Explicit Non-Goals

- No new charting dependency.
- No model leaderboard or statistical comparison.
- No changes to thesis evaluation data.
- No new discussion content or rewritten Q&A answers.
- No global presenter shortcut for the discussion index.
- No live LLM or chat work.
- No redesign of Scenes 1 through 12.
