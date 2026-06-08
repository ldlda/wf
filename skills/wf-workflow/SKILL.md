---
name: wf-workflow
description: Use when an agent needs to discover workflow capabilities, create or patch draft workspaces, save workflow or wrapper artifacts, deploy, run, resume, debug, or troubleshoot workflows in this repository.
---

# wf Workflow

Use this skill for the workflow lifecycle, regardless of front door:

- MCP tools exposed by `wf.workflow.*`
- repo-local `wf` CLI commands
- future `wf_api` callers

Prefer small discovery calls, draft workspaces, validation, and bounded trace
reads. Do not write raw workflow plans unless the user explicitly asks for the
low-level escape hatch.

## Workflow Lifecycle

1. Discover sources with `wf.admin.list_sources` or `wf cap list`.
2. Discover workflow-ready capabilities with `wf.workflow.list_capabilities`.
3. Inspect one candidate with `wf.workflow.inspect_capability`.
4. Call one candidate with `wf.workflow.call_capability` or `wf cap call` when
   payload shape or upstream source reachability is uncertain.
5. Create a patchable draft workspace with
   `wf.workflow.create_draft_workspace_from_capability`.
6. Patch targeted fields with focused helpers or JSON Patch.
7. Validate with `wf.workflow.validate_draft_workspace`.
8. Save with `wf.workflow.create_artifact_from_workspace` or
   `wf.workflow.create_wrapper_from_workspace`.
9. Save a deployment with `wf.workflow.save_deployment`.
10. Validate with `wf.workflow.validate_deployment`.
11. Run with `wf.workflow.run_deployment`.
12. Inspect stopped runs with `wf.workflow.inspect_run`; read bounded trace
    slices only when debugging.

## Rules

- Use workflow capabilities, not raw MCP tools, when building graphs.
- Use `call_capability` for single-call probes; use deployments/runs for durable
  lifecycle behavior.
- Treat wrapper hints as scaffolding, not semantic truth.
- Use draft workspaces for iterative authoring; avoid rewriting full drafts.
- Use explicit source bindings at deployment time.
- Keep traces bounded with `trace_range`.
- Do not expect a newly saved workflow to become a new MCP tool mid-session.
- For MCP content blocks, add explicit extraction/wrapper steps instead of
  pretending `content` is always plain text.

## References

Read only the reference needed for the current task. Start with a small preview
or search hit, then open the relevant section; do not dump every reference into
context.

Useful patterns:

```bash
# PowerShell preview
Get-Content skills/wf-workflow/references/workflow-lifecycle.md -TotalCount 40

# Targeted search
rg -n "trace|resume|binding_missing|wrapper_hints" skills/wf-workflow/references
```

- `references/workflow-lifecycle.md`: end-to-end lifecycle and tool order.
- `references/capabilities-and-wrappers.md`: raw capability vs workflow
  capability, wrapper artifacts, and content-block handling.
- `references/draft-workspaces.md`: draft shape, mappings, patches, and save
  path.
- `references/troubleshooting.md`: missing source/capability, unrunnable
  deployment, run/trace issues.

For shell-first workflows, also use the existing `wf-cli` skill.
