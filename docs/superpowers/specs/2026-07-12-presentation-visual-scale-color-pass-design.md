# Presentation Visual Scale And Color Pass Design

## Purpose

This slice improves the remaining weak presentation scenes without changing the
storyboard, RPC transport, live/replay behavior, chat framework, or workflow
facts. The target is a readable defense deck at both the adaptive 16:9 and 4:3
canvas shapes already supported by `/present`.

The presentation should feel like an intentional product explanation: one
dominant visual per beat, enough space to understand it, and restrained color
used to communicate state rather than decorate every surface.

## Current Problem

The current deck is functional but uneven. Some scenes still use too much
framing, too much blue on editorial surfaces, or too many small elements at
once. The main targets are:

- Scene 1 has weak title hierarchy, excess framing, and insufficient title-box
  padding/contrast.
- Scene 2 is taller and more card-like than a normal conversation/problem
  explanation should be; its editorial surface also carries unnecessary blue.
- Scene 7's authoring visuals are too small and Validate/Repair are not
  visually distinct enough across beats.
- Scene 9's lifecycle visuals lose scale when supporting chat and proof content
  compete with them.
- Scenes 13 and 14 rely on small diagrams or text blocks where one larger focal
  visual would carry the argument better.

## Scope

### In scope

- Scene 1 title hierarchy, padding, contrast, and removal of duplicate framing.
- Scene 2 composition height, visual balance, and non-demo color reduction.
- Scene 7 authoring visual scale and Validate/Repair distinction.
- Scene 9 prepared-lifecycle focal visual scale and supporting-surface balance.
- Scene 13 evaluation visual scale and information hierarchy.
- Scene 14 conclusion visual scale and removal of unnecessary blue.
- Screenshot smoke checks at `1280x720` and `1024x768`.
- Tests for stable structure, beat emphasis, and presentation-surface contracts.

### Out of scope

- Changing scene order, storyboard claims, or speaker script.
- Adding live workflow operations or changing replay truth.
- Replacing assistant-ui/shadcn chat components.
- Adding a real file browser to the Scene 10 input beat.
- Introducing a theme toggle or a third presentation theme.
- Rewriting the adaptive canvas or reintroducing `transform: scale(...)`.
- Reworking Scenes 3-6, 8, 10-12 unless a targeted regression is required.

## Design Rules

1. **One focal artifact per beat.** Supporting text, chat, receipts, and
   discussion affordances must not compete with the beat's main visual.
2. **Editorial surfaces are neutral.** Paper/editorial scenes may use cyan for
   a selected state or link, but should not be blue panels on white backgrounds.
3. **Demo surfaces keep operational color.** Scenes 8-12 may retain their
   darker operational treatment and state colors because they are the product
   demonstration. This is not a reason to recolor the rest of the deck.
4. **Scale before decoration.** Increase usable diagram area and reduce
   surrounding chrome before adding new labels, badges, or cards.
5. **Beat changes must be legible.** A changed beat should change emphasis,
   content, or position; do not rely on a tiny border or a nearly invisible
   opacity change.
6. **Use existing tokens and primitives.** Prefer existing editorial tokens,
   scene components, icons, figure layouts, and chat surfaces. Do not add a new
   generic card system for this pass.
7. **Protect the canvas.** Validate both supported aspect-ratio extremes. A
   diagram may scroll inside its own frame, but the presentation page must not
   acquire accidental outer scroll.

## Scene Targets

### Scene 1: Thesis

The title beat should read as a title page, not as a generic content card.
Keep the title, subtitle, and planner/tool/platform decomposition available
across beats, but establish a clear title-first hierarchy.

Acceptance points:

- One primary title treatment is visible; duplicate boxes do not frame the same
  content.
- Title padding is visibly generous at `1280x720`.
- Text contrast remains readable on the editorial surface.
- The decomposition can enter on later beats without shrinking the title beat.

### Scene 2: Problem

The scene should read left-to-right as a conversation/problem explanation, not
as two tall dashboard cards. Keep the transcript and reusable-automation
contrast, but make both blocks shorter and better balanced.

Acceptance points:

- The transcript reads as a chat/tool loop in normal reading order.
- The durable automation side is shorter and does not dominate by height.
- Blue is removed from the editorial background, borders, and decorative fills;
  only meaningful emphasis remains.
- The two sides remain understandable at `1024x768`.

### Scene 7: Author, Validate, Repair

The authoring loop is the visual argument. The active phase must become large
enough to explain while the rest of the loop remains a readable map.

Acceptance points:

- The loop has a clear primary visual and a compact phase rail.
- Validate shows diagnostics or contract checking as its own visual state.
- Repair shows a correction/revision state, not the same Validate card with a
  different label.
- Existing icons and factual commands remain available without turning the
  scene into a wall of CLI text.

### Scene 9: Prepared Workflow Lifecycle

The lifecycle scene should explain Draft, Artifact, Deployment, and Run with a
large lifecycle visual. The authoring assistant remains a supporting surface;
it must not compress the lifecycle into unreadable cards.

Acceptance points:

- The lifecycle rail or active phase occupies the dominant area.
- The active phase is readable at both canvas shapes.
- Chat and proof support remain present only where the beat calls for them.
- The scene does not duplicate the demo footer rail or live target badge.

### Scenes 13-14: Evaluation And Conclusion

These scenes should close with evidence and a clear contribution, not a dense
summary wall.

Acceptance points:

- Scene 13 gives the evaluation numbers one dominant visual treatment, with
  methodology limits as supporting content.
- Scene 14 gives the contribution/limits relationship one dominant visual
  treatment and removes unnecessary blue from the editorial surface.
- Icons or existing visual primitives may carry categories, but must not replace
  the factual labels needed for the defense.
- The final beat remains readable without opening a discussion panel.

## Verification Contract

- Existing presentation tests remain green.
- Add or update focused tests for Scene 1, Scene 2, Scene 7, Scene 9, Scene 13,
  and Scene 14 structure and beat emphasis.
- Verify no presentation route gets accidental outer scroll at `1280x720` and
  `1024x768`.
- Capture representative screenshots for the title, problem, authoring,
  lifecycle, evaluation, and conclusion scenes.
- Run `pnpm --dir web test`, `pnpm --dir web typecheck`, and
  `pnpm --dir web build` before completion.

## Deferred Follow-up: Real Input File Browser

The current Scene 10 input beat intentionally says `included in prepared run`.
That wording is factual, but it is not a file browser. A later slice may add a
real, read-only file browser for `#scene/run-from-deployment/input` backed by
the prepared recording and live run facts.

That follow-up must define what is actually known before showing it:

- canonical file paths and file count;
- whether a file was merely declared, selected, read, or produced;
- whether content preview is available from the live or replay source;
- how missing or unavailable previews are represented.

Until those facts exist, do not imply that the presentation selected or read
files merely because they appear in the prepared input manifest.
