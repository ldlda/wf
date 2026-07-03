---
name: "lda.chat Workflow Console"
description: "A product console and defense presentation surface for inspecting workflow lifecycle evidence."
colors:
  paper: "#faf8f5"
  ink: "#1a1a1a"
  slate: "#5a5a5a"
  surface: "#f0ede8"
  border: "#d4d0cb"
  signal-green: "#2d8a4e"
  amber: "#b8860b"
  red: "#c0392b"
  presentation-bg: "oklch(0.12 0.025 250)"
  presentation-panel: "oklch(0.18 0.025 250)"
  presentation-line: "oklch(0.36 0.04 250)"
  presentation-accent: "oklch(0.7 0.16 195)"
  presentation-interrupt: "oklch(0.76 0.18 70)"
typography:
  display:
    fontFamily: "Barlow Condensed, sans-serif"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "0.02em"
  body:
    fontFamily: "Source Sans 3, sans-serif"
    fontWeight: 400
    lineHeight: 1.5
  mono:
    fontFamily: "IBM Plex Mono, monospace"
    fontWeight: 400
    lineHeight: 1.4
rounded:
  control: "3px"
  surface: "4px"
  graph-node: "6px"
  presentation-panel: "0.85rem"
spacing:
  xs: "0.35rem"
  sm: "0.5rem"
  md: "0.75rem"
  lg: "1rem"
  xl: "1.25rem"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    rounded: "{rounded.control}"
    padding: "0.5rem 1.25rem"
  input-text:
    backgroundColor: "#ffffff"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "0.5rem 0.75rem"
  console-surface:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.surface}"
    padding: "1rem"
  presentation-panel:
    backgroundColor: "{colors.presentation-panel}"
    textColor: "oklch(0.96 0.01 250)"
    rounded: "{rounded.presentation-panel}"
    padding: "1rem"
---

# Design System: lda.chat Workflow Console

## 1. Overview

**Creative North Star: "The Evidence Theater"**

The console has two related visual modes. `/console` is a product tool: compact,
legible, and deliberately familiar. It should help an operator connect to a
workflow server, inspect records, and verify evidence without decoding raw JSON
first. `/present` is a defense surface: cinematic enough to keep attention, but
still grounded in real workflow operations, graph state, interrupt contracts,
and trace evidence.

This design system is transitional. The current implementation already has a
usable technical-console vocabulary and a separate dark presentation vocabulary,
but those token sets are not yet fully unified. Future visual work should
normalize the shared primitives before adding more styling.

The chat surface is not the core identity. Chat may frame a prepared operation
or narrate a workflow, but it must not become a hand-rolled generic chatbot. If
chat grows, use a mature assistant UI pattern and adapt it to the workflow
substrate.

**Key Characteristics:**

- Product console: readable, restrained, technical, evidence-first.
- Presentation route: cinematic, large-type, staged, graph-forward.
- Visual proof beats decorative flourish.
- Familiar product controls beat invented affordances.
- Chat stays professional and secondary.

## 2. Colors

The current palette is split between paper-console neutrals and a dark
presentation stage. Keep that split for now, but do not add a third unrelated
palette.

### Primary

- **Ink Black**: the console action and text anchor. Use for primary buttons,
  code panels, and high-emphasis text.
- **Presentation Cyan**: the presentation accent. Use for active beat rail
  items, selected graph nodes, and staged highlight moments only.

### Secondary

- **Signal Green**: success, connection, loaded/current status, and positive
  validation.
- **Interrupt Amber**: typed human boundary, review state, and interrupt graph
  emphasis.
- **Failure Red**: destructive or failed states only.

### Neutral

- **Warm Paper**: the current `/console` page background.
- **Stone Surface**: console sections, panels, and stable content blocks.
- **Soft Border**: console dividers, panel edges, and table rules.
- **Slate Text**: secondary labels, metadata, durations, and muted state text.
- **Night Stage**: the `/present` background and presentation canvas.

### Named Rules

**The One Evidence Accent Rule.** On any given screen, only one non-neutral color
should carry the user's attention. Green, amber, cyan, and red must not compete.

**The Palette Debt Rule.** Presentation OKLCH colors and console hex colors are
allowed today because they reflect existing code. New work should consolidate
them into named tokens instead of adding more one-off values.

## 3. Typography

**Display Font:** Barlow Condensed, sans-serif
**Body Font:** Source Sans 3, sans-serif
**Label/Mono Font:** IBM Plex Mono, monospace

**Character:** Condensed headings make the product feel operational and
technical without becoming terminal-only. Source Sans carries readable body
content. IBM Plex Mono is reserved for paths, commands, JSON, IDs, and evidence.

### Hierarchy

- **Display** (700, large route/beat headings, tight line-height): presentation
  stage titles and major defense beats.
- **Headline** (700, uppercase, `1.25rem` to `1.75rem`): console section titles
  and lifecycle panels.
- **Title** (600-700, uppercase, compact): card, graph node, and table group
  labels.
- **Body** (400, `1rem`, `1.5` line-height): explanatory copy, status text, and
  panel descriptions. Keep prose under 75ch where possible.
- **Label** (600, small, `0.05em` tracking): form labels, table headers, and
  compact metadata.
- **Mono** (`0.74rem` to `0.85rem`): commands, IDs, JSON, paths, run IDs, and
  equivalent CLI snippets.

### Named Rules

**The Mono Is Evidence Rule.** Monospace means something inspectable: a command,
path, ID, JSON body, or protocol field. Do not use mono as decoration.

**The Chat Restraint Rule.** Chat labels and messages should use the product
type system. Do not introduce playful display type inside the chat frame.

## 4. Elevation

The console is mostly flat and uses tonal layers, borders, and code panels for
depth. The workflow graph has a small mechanical shadow on nodes. Presentation
mode uses overlays and fixed drawers rather than heavy shadows.

### Shadow Vocabulary

- **Graph Node Lift** (`0 3px 0 rgba(26, 26, 26, 0.12)`): use only for graph
  nodes where the block needs a tangible, diagram-like presence.
- **Overlay Depth**: currently expressed through fixed positioning, darker
  surface color, and border contrast rather than a drop shadow.

### Named Rules

**The Flat By Default Rule.** Surfaces are separated with tone and borders.
Shadows are reserved for graph nodes or true overlays.

## 5. Components

### Buttons

- **Shape:** compact technical controls (`3px` radius).
- **Primary:** ink background, paper text, uppercase Barlow Condensed, `0.5rem`
  by `1.25rem` padding.
- **Hover / Focus:** hover lightens toward slate; focus must remain explicit and
  visible. Do not rely on color alone.
- **Presentation buttons:** may use darker panels and cyan selected states, but
  should keep predictable button affordances.

### Chips

- **Style:** the current system does not have a mature chip primitive. Use
  simple bordered labels or buttons until a component library lands.
- **State:** selected/current states should use the single active accent for the
  screen.

### Cards / Containers

- **Corner Style:** console panels use restrained corners (`4px`). Presentation
  panels use larger stage corners (`0.85rem`).
- **Background:** console panels use Stone Surface; presentation panels use dark
  Night Stage layers.
- **Shadow Strategy:** flat by default; see Elevation.
- **Border:** one-pixel structural borders are the default separator.
- **Internal Padding:** `1rem` for normal panels; tighter `0.6rem` to `0.75rem`
  for list and timeline items.

### Inputs / Fields

- **Style:** white field, ink text, mono type for URLs and command-like values,
  `3px` radius, one-pixel border.
- **Focus:** explicit green outline, not subtle glow.
- **Error / Disabled:** disabled controls lower opacity and preserve shape.
  Errors must include text; red alone is not enough.

### Navigation

- **Console navigation:** use familiar tabs/buttons for focus modes. Active
  state must be visible through class, text, or control state.
- **Presentation navigation:** beat rail is horizontal, keyboard-addressable,
  and should remain usable at 720p. Hash links identify beats.

### Workflow Graph

Workflow graph nodes are the signature component. They should feel like product
evidence, not decorative bubbles. Nodes use uppercase headings, mono references,
structural borders, and direct click targets. Interrupt nodes may use amber
border emphasis because the typed human boundary is conceptually important.

### Operation Block

Operation blocks show the tool call as a product event: equivalent CLI, raw
response, and interpreted response. The block should make the workflow substrate
legible without hiding raw evidence.

## 6. Do's and Don'ts

### Do:

- **Do** make the workflow graph, operation block, evidence drawer, lifecycle
  explorer, typed interrupt/resume panel, and trace the main visual surfaces.
- **Do** keep `/console` familiar and product-like: readable tables, standard
  buttons, clear labels, predictable focus states.
- **Do** let `/present` be cinematic with staged panels, larger text, and graph
  zooms, as long as each moment maps back to real evidence.
- **Do** use mature component and chat primitives when the interaction is
  standard.
- **Do** respect reduced motion and keep keyboard navigation reliable.
- **Do** use big text and few items during presentation beats.

### Don't:

- **Don't** make the console look like a generic AI chatbot.
- **Don't** hand-roll chat components as the foundation for the product.
- **Don't** let chat dominate presentation mode; it can slide in, collapse, or
  move off-screen.
- **Don't** use funny display fonts, doodle shapes, novelty bubbles, or unclear
  controls in the professional chat surface.
- **Don't** add decorative motion that does not explain state or guide attention.
- **Don't** overclaim a bundled autonomous AI-agent brain through UI copy.
- **Don't** add more one-off colors before normalizing the console and
  presentation token sets.
