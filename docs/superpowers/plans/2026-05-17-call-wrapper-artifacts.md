# Call Wrapper Artifacts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let `wf.workflow.call_capability` execute saved `WorkflowArtifact(kind="wrapper")` artifacts by their stable artifact node name without turning arbitrary saved workflows into node capabilities.

**Architecture:** Keep live `NodeSpec` execution unchanged. Extend the workflow surface resolution path so `workflow.<artifact_id>.v<version>` can resolve to a saved wrapper artifact, validate that it is wrapper-kind and interrupt-free, execute its stored plan through the existing workflow runner, and normalize the final workflow result into the same `qualified_name` / `outcome` / `output` payload shape as live capabilities.

**Tech Stack:** Python, Pydantic, `wf_artifacts`, `wf_core`, pytest.

---

### Task 1: Pin Wrapper-Artifact Call Semantics

**Files:**

- Modify: `tests/wf_mcp/test_service.py`

- [ ] **Step 1: Write the failing test**

Add a test that saves a wrapper artifact with a simple one-node plan, calls `WorkflowSurfaceHandlers.call_capability()` with `workflow.<id>.v<version>`, and asserts the returned `qualified_name`, `outcome`, and `output`.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --with pytest pytest tests/wf_mcp/test_service.py -q`

Expected: FAIL because `call_capability()` only resolves live specs today.

### Task 2: Resolve Wrapper Artifacts in the Workflow Surface

**Files:**

- Modify: `src/wf_mcp/workflow_surface/handlers.py`

- [ ] **Step 1: Implement minimal wrapper-artifact resolution**

Add a small helper that:

- recognizes stable artifact node names
- loads the artifact from the store
- rejects non-wrapper artifacts
- rejects unsupported interrupt plans
- executes the artifact plan with the existing workflow runner
- converts the workflow run into the `call_capability` response payload

- [ ] **Step 2: Run focused tests**

Run: `uv run --with pytest pytest tests/wf_mcp/test_service.py -q`

Expected: PASS.

### Task 3: Verify the Whole Project

**Files:**

- No additional files.

- [ ] **Step 1: Run focused workflow-surface tests**

Run: `uv run --with pytest pytest tests/wf_mcp -q`

Expected: PASS.

- [ ] **Step 2: Run the full suite**

Run: `uv run --with pytest pytest -q`

Expected: PASS.
