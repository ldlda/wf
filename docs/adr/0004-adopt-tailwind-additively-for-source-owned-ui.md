# Adopt Tailwind Additively For Source-Owned UI

Status: accepted

The web workspace will adopt Tailwind and shadcn-compatible conventions for
new source-owned chat and presentation primitives because established AI-chat
components provide better interaction and accessibility than maintaining a
custom message surface. Existing console CSS will not be rewritten wholesale;
old styles migrate only when their components are replaced.

## Considered Options

**Keep all styling hand-written.**
This avoids another styling dependency, but repeats low-level work for chat,
forms, focus states, and responsive composition. The existing presentation
already demonstrates the cost of one-off component styling.

**Rewrite the whole console with Tailwind and a component suite.**
This creates one styling mechanism eventually, but turns presentation work into
a risky console migration. It also lets framework defaults replace deliberate
product decisions before those decisions are ready.

**Adopt a complete AI application shell.**
This supplies familiar chat interactions quickly, but also imports model,
account, attachment, and transport assumptions that do not match the existing
`AgentDriver` and workflow RPC boundaries.

## Consequences

Tailwind enters through the official Vite integration without Preflight, so it
does not reset existing `/console` CSS. New source-owned primitives may follow
shadcn-compatible structure and copy narrowly selected open-source components,
while existing surfaces migrate only when replaced. The project retains
ownership of component code, accessibility, tokens, and domain behavior.
