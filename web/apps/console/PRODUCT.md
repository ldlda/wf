# Product

## Register

product

## Users

The primary users are the thesis author during defense preparation, demo
operators during a live presentation, and technical reviewers who need to see
how `lda.chat` works without reading raw workflow JSON. Secondary users are
future developers and agents using the console to inspect workflow lifecycle
records, source capabilities, runs, traces, and interrupt/resume boundaries.

Users are usually under time pressure: a defense, demo, review session, or
debugging pass. The interface should help them move quickly from a high-level
story to concrete evidence without forcing them to decode raw protocol payloads
first.

## Product Purpose

The console is the product-facing visual surface for `lda.chat`. It exists to
show that the workflow substrate is inspectable, operable, and explainable: an
operator can connect to a workflow server, inspect lifecycle records, view graph
structure, start or resume prepared workflows, and inspect raw/evaluated
evidence.

Presentation mode is not a generic slide deck. It is a cinematic product demo
surface for explaining the thesis: external planners propose actions, the
workflow substrate owns typed lifecycle state and deterministic execution, and
the resulting runs remain auditable through traces and evidence records.

Chat is a framing device, not the core product. It may introduce or narrate a
prepared workflow, but the main surfaces are the workflow graph, operation
blocks, evidence drawer, lifecycle explorer, typed interrupt/resume panel, and
run trace.

Success means a viewer can answer three questions quickly:

- What does `lda.chat` own that an external AI agent does not own?
- How does a workflow move from authoring to deployment to execution?
- Where is the proof that a specific run happened and can be inspected?

## Brand Personality

The product should feel precise, competent, and cinematic.

The console should feel like a real technical product: calm, readable, and
trustworthy. The presentation route may be more theatrical: large text, clear
beats, animated panels, graph zooms, and staged evidence reveals. The showmanship
must support understanding, not cover missing substance.

The desired feel is closer to a polished developer tool plus a live product
walkthrough than a generic AI chat app.

## Anti-references

Do not make the console look like a generic AI chatbot. Avoid hand-rolled chat
components as the design foundation; if chat becomes important, adopt or adapt a
mature open-source assistant UI pattern instead of inventing message bubbles,
tool-call affordances, and composer behavior from scratch.

Do not let chat dominate presentation mode. Chat can slide in, collapse, or move
off-screen, but the workflow graph and evidence views carry the thesis.

Do not use playful or decorative styling inside the professional chat surface:
no funny display fonts, doodle shapes, novelty bubbles, or unclear controls.

Do not build a sleep-inducing slide deck that only lists architecture claims.
The presentation should tell a story through staged transitions and concrete
workflow evidence.

Do not overclaim the presence of a bundled autonomous AI-agent brain. The product
surface may demonstrate a prepared or scripted agent-like interaction, but the
core contribution remains the workflow substrate.

## Design Principles

1. **Evidence first.** Every impressive visual should have a path back to a
   workflow record, operation, run trace, or captured protocol response.
2. **Graph over transcript.** Use chat sparingly; prefer graph, lifecycle,
   operation, and evidence views for explaining the system.
3. **Cinematic, not cluttered.** Use large text, few items, and staged motion for
   presentation mode. Avoid dense panels unless the viewer deliberately opens
   them.
4. **Professional where users operate.** The `/console` surface should prioritize
   familiar product patterns, predictable components, readable tables, and clear
   failure states.
5. **Agent-facing, not agent-theater.** Show how external agents or scripted demo
   flows operate `wf`; do not imply that the UI itself proves a new planning
   algorithm.
6. **Adopt standard primitives.** Prefer proven component libraries and mature
   chat UI patterns over custom controls when the interaction is standard.

## Accessibility & Inclusion

Target WCAG 2.2 AA for normal product UI. Presentation mode should remain usable
on a 720p projector or screen, with large text, high contrast, and no dependency
on color alone to distinguish models, stages, or outcomes.

Motion should respect `prefers-reduced-motion`. Presentation animations may be
cinematic, but they must not block comprehension, hide important content, or make
manual navigation difficult.

Keyboard navigation matters for defense use: arrow keys should move beats,
Escape should close overlays, and clickable graph nodes or drawers should remain
reachable through standard focus behavior.
