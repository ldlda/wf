# CodeRabbit Cleanup Follow-Ups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve non-blocking cleanup findings from the June 4 CodeRabbit review without mixing broad refactors into the focused correctness patch.

**Architecture:** Keep behavior unchanged unless a task explicitly says otherwise. Prefer documentation, small helpers, and narrowly scoped tests over cross-package refactors. Do not move modules or rename public APIs in this follow-up.

**Tech Stack:** Python 3.14, Pydantic v2, Typer, FastAPI JSON-RPC, pytest, ruff, basedpyright.

---

## Scope

This plan intentionally excludes the already-fixed review items:

- CLI config exception tuple syntax in `src/wf_cli/context.py`
- CLI source-registry file JSON object validation and exception chaining
- RPC method module structure-test coverage
- stale long-lived API and CLI/API alignment doc statuses
- typed `tmp_path` annotations in `tests/wf_config/test_config_models.py`

---

### Task 1: Document Source-Registry Mutation Asymmetry

**Files:**
- Modify: `docs/superpowers/plans/2026-06-04-source-registry-mutations.md`

- [ ] **Step 1: Add rationale under shadow handling**

Find the section mentioning:

```markdown
A future `allow_shadow` flag can relax add; do not add it in this slice.
```

Append:

```markdown
Rationale: `add` rejects config-shadowed ids to prevent silent no-ops: adding a
registry entry that cannot activate while config owns the same id. Existing
shadowed registry entries can still be updated, enabled, disabled, or removed so
operators can prepare store state for config removal or future `seed` ownership
policy.
```

- [ ] **Step 2: Verify doc diff**

Run:

```bash
git diff -- docs/superpowers/plans/2026-06-04-source-registry-mutations.md
```

Expected: only the rationale paragraph changed.

---

### Task 2: Clarify RPC Target Selection Precedence

**Files:**
- Modify: `docs/superpowers/plans/2026-06-03-workflow-config-and-rpc-cli-target.md`

- [ ] **Step 1: Add precedence table near the plan introduction**

Add:

```markdown
### Target Selection Precedence

1. `--url` CLI override selects an RPC HTTP target.
2. `--local` CLI override selects the in-process local target.
3. Config file `client.target` selects the configured target.
4. Missing target config defaults to local.

CLI overrides intentionally win over config so one-off diagnostics can point at
a different server without editing the config file.
```

- [ ] **Step 2: Verify no code references are changed**

Run:

```bash
git diff --stat
```

Expected: only the plan document is changed by this task.

---

### Task 3: Extract Source-Registry RPC Availability Helper

**Files:**
- Modify: `src/wf_transport_rpc_http/methods_source_registry.py`
- Test: `tests/wf_transport_rpc_http/test_source_registry_rpc.py`

- [ ] **Step 1: Add a helper**

In `src/wf_transport_rpc_http/methods_source_registry.py`, add:

```python
def _require_source_registry_admin(
    server: WorkflowServer,
    *,
    operation: str,
) -> WorkflowSourceRegistrySurface:
    admin = server.source_registry_admin
    if admin is None:
        raise WorkflowRpcError(
            data={
                "code": "source_registry_unavailable",
                "message": (
                    f"source registry admin {operation} are not available "
                    "for this server"
                ),
            }
        )
    return admin
```

Import `WorkflowSourceRegistrySurface` from `wf_api` if needed.

- [ ] **Step 2: Replace repeated `None` checks**

Use:

```python
admin = _require_source_registry_admin(server, operation="reads")
```

for list/inspect, and:

```python
admin = _require_source_registry_admin(server, operation="mutations")
```

for add/update/enable/disable/remove.

- [ ] **Step 3: Run source-registry RPC tests**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_source_registry_rpc.py -q
```

Expected: all tests pass.

---

### Task 4: Clarify Chronological Event Ordering

**Files:**
- Modify: `src/wf_api/admin.py`
- Test: existing admin API tests if present

- [ ] **Step 1: Add a comment above `list_events`**

Add a short comment/docstring note near `WorkflowAdminApi.list_events`:

```python
# Preserve provider order for events; event providers are expected to return
# chronological order and callers may rely on that ordering for diagnostics.
```

Do not sort event payloads in this task.

- [ ] **Step 2: Run admin API tests**

Run:

```bash
uv run pytest tests/wf_api -q
```

Expected: all `wf_api` tests pass.

---

### Task 5: Record Shared ID Pattern Follow-Up

**Files:**
- Modify: `docs/current_roadmap.md`

- [ ] **Step 1: Add a small platform cleanup bullet**

Under the platform cleanup/architecture section, add:

```markdown
- Cleanup candidate: consolidate store/source registry id validation patterns
  (`SOURCE_REGISTRY_ID_PATTERN`, `STORE_ID_PATTERN`) only after another package
  needs the same rule. Today they intentionally stay close to their stores.
```

- [ ] **Step 2: Verify docs only**

Run:

```bash
git diff -- docs/current_roadmap.md
```

Expected: only the cleanup bullet changed.

---

## Final Verification

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_source_registry_rpc.py tests/wf_api -q
uv run ruff check src/wf_transport_rpc_http/methods_source_registry.py src/wf_api/admin.py docs/superpowers/plans/2026-06-04-source-registry-mutations.md docs/superpowers/plans/2026-06-03-workflow-config-and-rpc-cli-target.md docs/current_roadmap.md
uv run basedpyright --level error src/wf_transport_rpc_http/methods_source_registry.py src/wf_api/admin.py
git diff --check
```

Expected: pytest exits 0, ruff exits 0, basedpyright exits 0, and `git diff --check` reports no whitespace errors.
