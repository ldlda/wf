# Workflow Skill Docs Mirror Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a repo-local `wf-workflow` skill with agent-facing references and expose those same skill files through the MCP documentation source.

**Architecture:** `docs/` remains project-facing documentation. `skills/wf-workflow/` becomes a self-contained agent-facing operating manual with distilled references. `src/wf_mcp/documentation.py` exposes the skill files as documentation resources under `wf://skills/...` without changing existing `wf://docs/...` resources.

**Tech Stack:** Markdown skills, `wf_mcp.documentation`, `wf_platform.DocumentationResource`, pytest.

---

## Tasks

- [ ] Add a failing docs resource test for `wf://skills/wf-workflow/SKILL.md` and one reference.
- [ ] Create `skills/wf-workflow/SKILL.md`.
- [ ] Create `skills/wf-workflow/references/workflow-lifecycle.md`.
- [ ] Create `skills/wf-workflow/references/capabilities-and-wrappers.md`.
- [ ] Create `skills/wf-workflow/references/draft-workspaces.md`.
- [ ] Create `skills/wf-workflow/references/troubleshooting.md`.
- [ ] Update `src/wf_mcp/documentation.py` to load the skill files as resources.
- [ ] Verify focused docs tests and lint.

## Guardrails

- Do not replace the existing `skills/wf-cli` skill.
- Do not make `SKILL.md` a link-only file.
- Do not symlink skill references to `docs/`; checked-in distilled files are more portable.
- Do not remove existing `wf://docs/...` resources.
