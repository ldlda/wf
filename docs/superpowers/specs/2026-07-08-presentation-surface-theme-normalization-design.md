# Presentation Surface Theme Normalization Design

## Purpose

The previous contrast pass fixed dark-on-dark text, but it did not make the
presentation side-surfaces feel coherent. Chat can become too white, while
discussion/Q&A panels still use a dark modal interior. This slice normalizes
those surfaces so `/present` reads as one editorial product walkthrough instead
of multiple unrelated UI skins.

## Scope

In scope:

- Chat rail and chat message surface styling.
- Discussion panel and Q&A branch styling.
- Presenter-note styling inside discussion panels.
- Shared presentation-only CSS hooks for editorial and night side-surfaces.
- Screenshot smoke for representative scenes and direct discussion hashes.

Out of scope:

- Replacing chat with AI Elements or another chat framework.
- Scene 6/7/10 composition changes.
- Schema form approval UI.
- Guided run beat gates.
- Presenter companion.
- Global `/console` theme changes.

## Design Direction

Use one restrained editorial surface vocabulary for presentation side-surfaces:

- **Editorial surface**: off-paper, slightly tinted, readable dark ink, subtle
  border, used for light chat and discussion panels.
- **Night surface**: dark, readable text, restrained cyan/amber accents, used
  only when a beat intentionally lives on the dark workflow stage.

Do not let chat become pure white cards floating on paper. Do not let discussion
modals look like old dark dashboard cards when opened from paper scenes. The
modal should feel like a focused editorial note: readable, calm, and connected
to the presentation canvas.

## Surface Contract

Components that render side-surfaces should expose a semantic surface attribute:

```tsx
data-presentation-surface="editorial" | "night"
```

This is not a full theme system. It is a small CSS contract for presentation
side-surfaces. It should live on:

- `OperatorChat`
- `DiscussionPanel`

Existing `data-chat-theme` may remain for compatibility, but CSS should prefer
the semantic surface attribute for visual styling.

## Chat

Light chat should use the editorial surface, not white cards. The chat rail
should be readable but secondary to the graph/evidence surfaces.

Required:

- `OperatorChat` maps `chatTheme === "light"` to
  `data-presentation-surface="editorial"`.
- Chat cards on the editorial surface use off-paper background and dark ink.
- Tool-call parts inside chat use the same surface, border, and text rules.
- Night chat stays readable with dark cards and light text.

## Discussion/Q&A

All direct `#discuss/...` routes should use the editorial surface by default.
This keeps Q&A readable and avoids dark modal interiors on paper scenes.

Required:

- `DiscussionPanel` root uses `data-presentation-surface="editorial"`.
- Title, badge, evidence pointer, summary, Q&A answer, details, links, return
  button, and presenter note all have explicit readable colors.
- Presenter notes stay demoted: visible to presenter, not styled as the main
  answer.

## Testing And Smoke

Automated tests should pin the surface attributes and representative content.
CSS color correctness is confirmed through screenshot smoke, not jsdom computed
color assertions.

Screenshot smoke targets:

- `#scene/positioning/landscape`
- `#scene/planner-runtime/planner`
- `#scene/lifecycle/draft`
- `#discuss/where-is-ai-agent`
- `#discuss/evaluation-validity`
- `#scene/interrupt-evidence/approval`

Acceptance:

- Chat is not pure white unless intentionally inside a full paper scene.
- Discussion panels are readable and editorial.
- Q&A panels do not look like old dashboard modals.
- Presenter notes are demoted but legible.
- `/console` remains unaffected.
