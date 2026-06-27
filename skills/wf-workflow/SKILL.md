---
name: wf-workflow
description: Use when an agent needs to discover workflow capabilities, create or patch draft workspaces, save workflow or wrapper artifacts, deploy, run, resume, debug, or troubleshoot workflows in this repository.
---

# wf Workflow

Use this skill for the workflow lifecycle when the available front door is the
repo-local `wf` CLI.

Prefer small discovery calls, draft workspaces, validation, and bounded trace
reads. Do not write raw workflow plans unless the user explicitly asks for the
low-level escape hatch or you already have a complete compiler/generated plan.

## Workflow Lifecycle

1. Discover available capabilities with `wf cap list`.
2. Inspect one candidate with `wf cap inspect`.
3. Call one candidate with `wf cap call` when payload shape or upstream source
   reachability is uncertain.
4. Create a patchable draft workspace with `wf draft create --capability`.
5. Patch targeted fields with focused draft commands or JSON Patch.
6. Validate with `wf draft validate`.
7. Save an artifact with `wf draft save`, or import a complete raw plan with
   `wf artifact create-from-plan`.
8. Save a deployment with `wf deploy save` or `wf deploy create`.
9. Validate with `wf deploy validate`.
10. Run with `wf run start`.
11. Inspect stopped runs with `wf run inspect`; read bounded trace
    slices only when debugging.

## Rules

- Use workflow capabilities, not raw MCP tools, when building graphs.
- Use `call_capability` for single-call probes; use deployments/runs for durable
  lifecycle behavior.
- Treat wrapper hints as scaffolding, not semantic truth.
- Use draft workspaces for iterative authoring; avoid rewriting full drafts.
- Prefer focused draft edit commands before hand-writing JSON Patch.
- If a complete raw JSON/YAML plan already exists, the CLI escape hatch is
  `wf artifact create-from-plan`; do not write helper scripts that call
  internal APIs directly.
- Use `artifact create-from-plan` only for complete raw plans; do not pass draft
  JSON to it.
- Use explicit source bindings at deployment time.
- Keep traces bounded with `trace_range`.
- Do not expect a newly saved workflow to become a new MCP tool mid-session.
- For MCP content blocks, add explicit extraction/wrapper steps instead of
  pretending `content` is always plain text.

## References

Read only the reference needed for the current task:

- Start with `system-model.md` when lifecycle vocabulary is unclear.
- Use `workflow-lifecycle.md` for operation order.
- Use `capabilities-and-wrappers.md` before selecting a source capability.
- Use `draft-workspaces.md` for iterative editing.
- Use `direct-plan-import.md` only when a complete raw plan is required.
- Use `troubleshooting.md` after a public validation/run failure.

Before authoring JSON, query the live public model with `wf schema`; the
references explain semantics while the command reflects the current shape.

Useful patterns:

```bash
# PowerShell preview
Get-Content skills/wf-workflow/references/system-model.md -TotalCount 80

# Targeted search
rg -n "trace|resume|binding_missing|wrapper_hints" skills/wf-workflow/references
```

- `references/system-model.md`: short explanation of how sources,
  capabilities, drafts, artifacts, deployments, runs, bindings, and traces fit
  together.
- `references/workflow-lifecycle.md`: end-to-end lifecycle and tool order.
- `references/capabilities-and-wrappers.md`: raw capability vs workflow
  capability, wrapper artifacts, and content-block handling.
- `references/draft-workspaces.md`: draft shape, mappings, patches, and save
  path.
- `references/direct-plan-import.md`: complete workflow plan JSON shape for
  `wf artifact create-from-plan`.
- `references/troubleshooting.md`: missing source/capability, unrunnable
  deployment, run/trace issues.

For shell-first workflows, also use the existing `wf-cli` skill.
