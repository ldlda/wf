# Presentation Opening Visuals Design

## Purpose

Scenes 1 and 2 currently start the defense with too much text and too little
visual argument. The opening should make the thesis title defensible before the
technical slides begin: the project started as an AI-agent ambition, but the
implemented contribution is the workflow platform layer that makes external
agents useful for reusable workspace automation.

The opening must feel like a story, not a disclaimer.

## Core Framing

The first minute should use an origin-story stance:

```text
I wanted to build an AI agent for workspace workflows.
I found that the durable platform underneath the agent was the hard part.
This thesis focuses on that platform layer.
```

The title should decompose into three conceptual parts:

```text
Planner -> Tool Surface -> Workflow Platform
```

Known products should appear only where they clarify the model:

- `Codex`, `Claude`, and `OpenCode` sit under `Planner`.
- `CLI`, `MCP`, and `APIs` sit under `Tool Surface`.
- The submitted work is highlighted under `Workflow Platform` as the local
  workflow substrate implementation. The decomposition should not rely on the
  project name alone to explain the category.

Do not introduce `wf` CLI branding in the opening. The CLI appears later as one
implementation surface.

## Scene 1: Thesis Origin

Scene 1 should have two beats.

### Beat 1: Title reveal

Primary visual:

- A cinematic title reveal using the real thesis title.
- The title should be readable at 720p and not collapse into a wall of text.
- The subtitle may keep the forced "AI Agent" wording, but the animation should
  prepare the decomposition that follows.

Required visual elements:

- Large title typography.
- Three faint latent components behind or below the title: `Planner`,
  `Tool Surface`, `Workflow Platform`.
- Simple iconography for the three components:
  - Planner: model/chat/brain-like symbol.
  - Tool Surface: terminal/API/plug-like symbol.
  - Workflow Platform: durable graph/store/records-like symbol.

### Beat 2: Contribution focus

Primary visual:

```text
Planner             Tool Surface           Workflow Platform
Codex / Claude      CLI / MCP / APIs        submitted substrate
OpenCode                                  Typed · Durable · Inspectable
```

The workflow-platform block should become dominant. Avoid `wf` branding here;
the CLI is an implementation surface introduced later.

Required behavior:

- The visual emphasis moves from the whole "AI agent" phrase to the platform
  block.
- A defense question pill remains available: `Where is the AI agent?`
- The main slide body should not say "this thesis does not implement a new
  autonomous planning algorithm." That sentence belongs in speaker notes or the
  Q&A branch, not the primary visual.

Speaker-script intent:

```text
By AI agent, I do not mean I built a new Codex, Claude, or OpenCode. Existing
agents can already plan and call tools. I focused on the workflow platform
layer: the part that makes their work typed, durable, inspectable, and reusable.
```

## Scene 2: From Action Sequence To Automation

Scene 2 should also have two beats.

### Beat 1: Agent loop

Primary visual:

```text
Action sequence
think -> tool -> observe -> tool -> done
```

The left side should show a transcript/action sequence that can prove what
happened once but does not itself become reusable automation.

Required visual elements:

- Small, recognizable action icons: thought bubble, tool call, observation,
  second tool call, done marker.
- The transcript should visually fade, compress, or trail off. It should not be
  framed as useless; it is useful but insufficient.

### Beat 2: Reusable automation

Primary visual:

```text
Reusable automation
design -> save -> connect -> run -> inspect
```

Use simple verbs. Do not introduce the formal lifecycle terms
`Draft / Artifact / Deployment / Run / Trace` yet. Those belong in Scene 5.

Required visual elements:

- Five concrete icons:
  - Design: pencil/diagram.
  - Save: versioned file/artifact.
  - Connect: plug/binding.
  - Run: play/execution.
  - Inspect: magnifier/trace.
- A persistent container or rail that implies durability across time.
- A short contrast line:
  `The agent loop acts once. The platform makes work reusable.`

Speaker-script intent:

```text
The problem is not whether an agent can act. The problem is whether its action
becomes something reusable. A transcript can prove what happened, but workspace
automation needs a platform that can design, save, connect, run, and inspect the
work.
```

## Visual Requirements

- Use icons and shapes, not text-only lists.
- Avoid overusing generic cards. Prefer one dominant diagram per beat.
- Keep copy large enough for a 720p display.
- Motion should be scripted, not interactive. Save click/zoom interactions for
  architecture, demo, and Q&A scenes.
- The opening should be confident. Avoid defensive wording in the main visual.
- Scenes 3, 4, and 5 are baseline-good and out of scope for this slice.

## Data And Components

Likely implementation targets:

- `web/apps/console/src/presentation/storyboard.ts`
- `web/apps/console/src/presentation/SceneBody.tsx`
- `web/apps/console/src/presentation/presentation.css`
- New focused components are acceptable if they keep `SceneBody.tsx` lean.

Suggested component split:

- `OpeningThesisScene`: title reveal and decomposition.
- `ProblemLoopScene`: action sequence vs reusable automation.
- Optional shared `ConceptIcon` if icons stay inline/SVG.

Prefer source-owned reusable presentation primitives for chips, icon plaques,
timeline steps, and placeholder surfaces. If a component library is introduced
later for chat or product surfaces, the opening visuals should be able to reuse
that visual language instead of growing a separate ad-hoc illustration style.
Hand-authored SVG/CSS is acceptable for a small number of stable concept icons,
but do not add a new icon package unless the implementation plan justifies it.

## Tests

Add tests that pin behavior without overfitting animation details:

- Scene 1 renders `Planner`, `Tool Surface`, `Workflow Platform`, known agent
  names, the submitted substrate/platform block, and
  `Typed · Durable · Inspectable`.
- Scene 1 exposes a `Where is the AI agent?` discussion action.
- Scene 2 renders `Action sequence` and `Reusable automation`.
- Scene 2 uses simple verbs: `design`, `save`, `connect`, `run`, `inspect`.
- Scene 2 does not render formal lifecycle names before Scene 5.

Visual smoke should capture:

- `#scene/thesis/title`
- `#scene/thesis/substrate`
- `#scene/problem/direct-actions`
- `#scene/problem/missing-contracts`

## Out Of Scope

- Redesigning Scenes 3, 4, or 5.
- Changing thesis title text.
- Adding live LLM behavior.
- Reworking the report workflow demo.
- Adding named related-system comparisons before Scene 3.
