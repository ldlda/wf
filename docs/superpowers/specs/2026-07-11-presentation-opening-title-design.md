# Presentation Opening Title Design

## Status

Proposed implementation slice. This document replaces the earlier Scene 1
assumption that its opening visual pass is complete.

## Purpose

Scene 1 must introduce the thesis as an agent-shaped product goal without
trying to explain the automation problem before Scene 2. It should tell the
audience what the title means and precisely identify the implemented part.

## Narrative Boundary

- Scene 1 answers: What is the product goal, and which part is implemented?
- Scene 2 answers: Why are direct agent actions not reusable automation?
- Scene 1 must not use a generic label such as `Thesis` or `Decomposed` as its
  dominant display copy.
- Scene 1 must not lead with the workflow substrate's detailed benefits. Those
  belong to Scene 2 and later lifecycle/architecture scenes.

## Composition

The scene retains the compact formal title `Design and Implementation of
lda.chat` in the stage caption. Its main focal copy is:

> An AI Agent for Workspace Workflows

Under it, one connected horizontal system shows three roles in sequence:

```text
Planner  ->  Tool surface  ->  Runner / platform
```

The roles are structural parts of one agent-shaped product, not independent
feature cards. Their labels and supporting examples are:

| Role | Supporting label |
|---|---|
| Planner | Codex, Claude, OpenCode |
| Tool surface | CLI, MCP, JSON-RPC |
| Runner / platform | workflow lifecycle and deterministic execution |

The first beat keeps the three roles equally legible. The second beat enlarges
and visually selects `Runner / platform`, retains the other two roles as
connected context, and adds the exact label `Implemented contribution`.

The selected role may expose a short, factual scope line: `Lifecycle,
validation, records, traces, and interrupt/resume`. It must remain supporting
copy, not a second oversized headline.

## Visual Direction

- Use the existing editorial canvas, presentation type, and one cyan active
  accent. Do not introduce a new theme or blue decorative treatment.
- Use the existing concept icon vocabulary only when it reinforces each role;
  the connection line and role hierarchy are the primary visual structure.
- Avoid three same-weight card panels. The system must visibly read left to
  right, with a meaningful destination at `Runner / platform`.
- At 1280x720, the main title and all three role names must be readable without
  competing with the stage caption, discussion rail, or footer.
- Motion is limited to a short role-focus transition between beats. Reduced
  motion uses the final static state.

## Acceptance Criteria

1. The first beat's largest text is `An AI Agent for Workspace Workflows`.
2. Neither `Thesis` nor `Decomposed` is rendered as a display heading.
3. The role sequence renders as connected agent context, not three detached
   cards.
4. The second beat labels only `Runner / platform` as `Implemented
   contribution` and keeps planner/tool surface visible as context.
5. Scene 2 remains responsible for the direct-actions-versus-reusable-
   automation argument.
6. Unit tests cover both beats' focus and display copy; browser screenshots at
   1280x720 cover both beats without clipping.
