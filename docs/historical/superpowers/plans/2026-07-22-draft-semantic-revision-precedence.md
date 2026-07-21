# Draft Semantic Revision Precedence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure every content-aware draft authoring helper returns the canonical `revision_conflict` result before inspecting current draft content or capability metadata for a stale request.

**Architecture:** Reuse `WorkflowDraftAuthoringApi._workspace_if_revision_matches` as the shared semantic preflight for all seven affected helpers. Keep `WorkflowDraftApi.patch_draft_workspace` as the second, mutation-time optimistic-lock guard so public error precedence is deterministic without weakening race safety.

**Tech Stack:** Python 3.14, pytest with pytest-asyncio, Ruff, basedpyright

## Global Constraints

- Follow [`draft semantic revision precedence design`](../../../superpowers/specs/2026-07-22-draft-semantic-revision-precedence-design.md).
- Request-envelope validation that does not read workspace or catalog state remains before revision preflight.
- After envelope validation, stale revision conflict wins over all workspace-content and capability-catalog errors.
- Missing-workspace behavior remains unchanged.
- Current-revision semantic errors, successful edit shapes, and no-op revision behavior remain unchanged.
- Every mutation still delegates to `patch_draft_workspace`; do not replace or bypass its mutation-time revision check.
- Do not change Python API, JSON-RPC, remote-client, CLI, or TypeScript signatures.
- Do not add a decorator, exception-translation layer, new storage API, or compatibility branch.
- Do not stage or modify the ACL-protected untracked `pytest-of-lda/` directory.

---

## File Map

- Modify `src/wf_api/draft_authoring.py`: generalize the revision helper and move all seven semantic helpers behind it.
- Modify `tests/wf_api/test_drafts_service.py`: add stale-plus-semantic-defect regressions, envelope-precedence coverage, and a direct mutation-guard characterization.
- Modify `ISSUES.md`: check only the resolved `Draft revision semantics` item after all gates pass.
- Modify `docs/current_roadmap.md`: add the completed slice with a link to the archived plan.
- Move this plan to `docs/historical/superpowers/plans/2026-07-22-draft-semantic-revision-precedence.md` after completion.

### Task 1: Gate Capability-Aware Semantic Edits

**Files:**
- Modify: `src/wf_api/draft_authoring.py:104-124`
- Modify: `src/wf_api/draft_authoring.py:323-694`
- Test: `tests/wf_api/test_drafts_service.py`

**Interfaces:**
- Consumes: `WorkflowDraftAuthoringApi._workspace_if_revision_matches(*, workspace_id: str, revision: int) -> WorkflowDraftWorkspace | dict[str, Any]`.
- Produces: unchanged `bind_draft(...) -> dict[str, Any]` and `add_step_from_capability(...) -> dict[str, Any]` behavior, with revision preflight before `draft_step`, schema projection, or capability lookup.
- Preserves: `WorkflowDraftApi.patch_draft_workspace(...)` as the final mutation-time guard.

- [x] **Step 1: Add a direct characterization test for the final mutation guard**

  Add this test near `test_patch_draft_workspace_updates_revision` in `tests/wf_api/test_drafts_service.py`:

  ```python
  @pytest.mark.asyncio
  async def test_patch_draft_workspace_stale_revision_does_not_mutate(
      tmp_path: Path,
  ) -> None:
      artifact_store = FileWorkflowArtifactStore(
          tmp_path / "drafts_patch_workspace_stale"
      )
      api, _service, _authoring = _draft_api(artifact_store, register_echo=True)
      await api.create_draft_workspace(
          workspace_id="echo_ws",
          draft=_echo_draft(),
      )
      before = await api.get_draft_workspace(
          workspace_id="echo_ws",
          include_draft=True,
      )

      result = await api.patch_draft_workspace(
          workspace_id="echo_ws",
          revision=2,
          patch=[{"op": "replace", "path": "/name", "value": "must_not_apply"}],
      )

      after = await api.get_draft_workspace(
          workspace_id="echo_ws",
          include_draft=True,
      )
      assert result["status"] == "conflict"
      assert result["diagnostics"][0]["code"] == "revision_conflict"
      assert after == before
  ```

- [x] **Step 2: Run the mutation-guard characterization**

  Run:

  ```powershell
  uv run pytest tests/wf_api/test_drafts_service.py::test_patch_draft_workspace_stale_revision_does_not_mutate -q -n 0 --basetemp C:\tmp\pytest-draft-revision-guard
  ```

  Expected: PASS before production changes. This pins the existing second revision check that the semantic preflight must not replace.

- [x] **Step 3: Add failing stale-versus-capability-semantic tests**

  Add this test near `test_add_step_stale_revision_wins_over_content_preflight`:

  ```python
  @pytest.mark.asyncio
  @pytest.mark.parametrize("operation", ["bind", "capability_add"])
  async def test_capability_aware_edits_stale_revision_wins_over_semantic_errors(
      tmp_path: Path,
      operation: str,
  ) -> None:
      artifact_store = FileWorkflowArtifactStore(
          tmp_path / f"draft_capability_stale_{operation}"
      )
      api, _service, authoring = _draft_api(artifact_store, register_echo=True)
      await api.create_draft_workspace(
          workspace_id="draft_ws",
          draft=_echo_draft(),
      )
      before = await api.get_draft_workspace(
          workspace_id="draft_ws",
          include_draft=True,
      )

      if operation == "bind":
          result = await authoring.bind_draft(
              workspace_id="draft_ws",
              revision=2,
              step_id="missing",
              source_path="input.text",
              target_path="local.text",
          )
      else:
          result = await authoring.add_step_from_capability(
              workspace_id="draft_ws",
              revision=2,
              step_id="new_step",
              capability_name="missing.connection.unknown_tool",
          )

      after = await api.get_draft_workspace(
          workspace_id="draft_ws",
          include_draft=True,
      )
      assert result["status"] == "conflict"
      assert result["revision"] == before["revision"]
      assert result["diagnostics"][0]["code"] == "revision_conflict"
      assert after == before
  ```

- [x] **Step 4: Run the new semantic-precedence test and confirm it is red**

  Run:

  ```powershell
  uv run pytest tests/wf_api/test_drafts_service.py::test_capability_aware_edits_stale_revision_wins_over_semantic_errors -q -n 0 --basetemp C:\tmp\pytest-draft-revision-capability-red
  ```

  Expected: FAIL because `bind_draft` raises for the missing step and `add_step_from_capability` raises during unknown capability lookup before returning a conflict.

- [x] **Step 5: Generalize the shared revision helper documentation**

  In `WorkflowDraftAuthoringApi._workspace_if_revision_matches`, replace the no-op-specific docstring with:

  ```python
  """Load a workspace and enforce optimistic locking before semantic preflight."""
  ```

  Keep its return shape and diagnostic construction unchanged.

- [x] **Step 6: Gate `bind_draft` before draft and catalog inspection**

  Replace the direct workspace load at the start of `bind_draft` with:

  ```python
  checked = self._workspace_if_revision_matches(
      workspace_id=workspace_id,
      revision=revision,
  )
  if isinstance(checked, dict):
      return checked
  workspace = checked
  ```

  Leave all subsequent `draft_step`, capability lookup, path parsing, schema projection, and patch construction unchanged.

- [x] **Step 7: Gate `add_step_from_capability` before draft and catalog inspection**

  Replace the direct workspace load at the start of `add_step_from_capability` with:

  ```python
  checked = self._workspace_if_revision_matches(
      workspace_id=workspace_id,
      revision=revision,
  )
  if isinstance(checked, dict):
      return checked
  workspace = checked
  ```

  This block must precede `workspace.draft.get("steps")` and `self.context.specs.get_qualified_spec(capability_name)`.

- [x] **Step 8: Run focused capability-aware tests**

  Run:

  ```powershell
  uv run pytest tests/wf_api/test_drafts_service.py -q -n 0 --basetemp C:\tmp\pytest-draft-revision-capability -k 'bind_draft or add_step_from_capability or patch_draft_workspace_stale_revision'
  ```

  Expected: PASS. Existing current-revision bind and capability-add success/error tests must remain unchanged.

- [x] **Step 9: Run focused quality checks**

  Run:

  ```powershell
  uv run ruff check src/wf_api/draft_authoring.py tests/wf_api/test_drafts_service.py
  uv run ruff format --check src/wf_api/draft_authoring.py tests/wf_api/test_drafts_service.py
  uv run basedpyright src/wf_api/draft_authoring.py tests/wf_api/test_drafts_service.py --level error
  ```

  Expected: all commands exit 0.

- [x] **Step 10: Commit Task 1**

  ```powershell
  git add src/wf_api/draft_authoring.py tests/wf_api/test_drafts_service.py
  git commit -m "fix: gate capability draft edits on revision"
  ```

### Task 2: Normalize Route And Removal Revision Precedence

**Files:**
- Modify: `src/wf_api/draft_authoring.py:694-925`
- Test: `tests/wf_api/test_drafts_service.py`

**Interfaces:**
- Consumes: the generalized `_workspace_if_revision_matches` from Task 1.
- Produces: unchanged `branch_draft`, `handle_draft`, `remove_draft_route`, `remove_draft_step`, and `remove_draft_binding` signatures with one early revision gate each.
- Preserves: the request-envelope `remove_draft_binding` selection check before workspace lookup and all current-revision no-op summaries without revision increments.

- [x] **Step 1: Add failing stale-versus-content-semantic tests**

  Add these tests in the branch/handle and remove-helper section of `tests/wf_api/test_drafts_service.py`:

  ```python
  @pytest.mark.asyncio
  @pytest.mark.parametrize(
      "operation",
      ["branch", "handle", "remove_route", "remove_step", "remove_binding"],
  )
  async def test_route_and_remove_edits_stale_revision_wins_over_semantic_errors(
      tmp_path: Path,
      operation: str,
  ) -> None:
      artifact_store = FileWorkflowArtifactStore(
          tmp_path / f"draft_route_remove_stale_{operation}"
      )
      api, _service, authoring = _draft_api(artifact_store, register_echo=True)
      draft = _echo_draft()
      if operation in {"branch", "handle", "remove_route"}:
          draft["routes"] = "not-an-object"
      elif operation == "remove_step":
          draft["steps"] = "not-an-object"
      await api.create_draft_workspace(workspace_id="draft_ws", draft=draft)
      before = await api.get_draft_workspace(
          workspace_id="draft_ws",
          include_draft=True,
      )

      if operation == "branch":
          result = await authoring.branch_draft(
              workspace_id="draft_ws",
              revision=2,
              step_id="echo",
              routes={"error": "__end__"},
          )
      elif operation == "handle":
          result = await authoring.handle_draft(
              workspace_id="draft_ws",
              revision=2,
              branches=[RouteSource(step_id="echo", outcome="error")],
              target="__end__",
          )
      elif operation == "remove_route":
          result = await authoring.remove_draft_route(
              workspace_id="draft_ws",
              revision=2,
              step_id="echo",
              outcome="ok",
          )
      elif operation == "remove_step":
          result = await authoring.remove_draft_step(
              workspace_id="draft_ws",
              revision=2,
              step_id="echo",
          )
      else:
          result = await authoring.remove_draft_binding(
              workspace_id="draft_ws",
              revision=2,
              step_id="missing",
              inputs=("text",),
          )

      after = await api.get_draft_workspace(
          workspace_id="draft_ws",
          include_draft=True,
      )
      assert result["status"] == "conflict"
      assert result["revision"] == before["revision"]
      assert result["diagnostics"][0]["code"] == "revision_conflict"
      assert after == before


  @pytest.mark.asyncio
  async def test_remove_draft_binding_envelope_error_precedes_revision_check(
      tmp_path: Path,
  ) -> None:
      artifact_store = FileWorkflowArtifactStore(
          tmp_path / "draft_remove_binding_envelope_precedence"
      )
      api, _service, authoring = _draft_api(artifact_store, register_echo=True)
      await api.create_draft_workspace(workspace_id="draft_ws", draft=_echo_draft())
      before = await api.get_draft_workspace(
          workspace_id="draft_ws",
          include_draft=True,
      )

      with pytest.raises(
          ValueError,
          match="pass at least one input or output binding to remove",
      ):
          await authoring.remove_draft_binding(
              workspace_id="draft_ws",
              revision=2,
              step_id="echo",
          )

      after = await api.get_draft_workspace(
          workspace_id="draft_ws",
          include_draft=True,
      )
      assert after == before
  ```

- [x] **Step 2: Run the new route/removal tests and confirm the semantic cases are red**

  Run:

  ```powershell
  uv run pytest tests/wf_api/test_drafts_service.py -q -n 0 --basetemp C:\tmp\pytest-draft-revision-route-red -k 'route_and_remove_edits_stale_revision or remove_draft_binding_envelope_error'
  ```

  Expected: the five parameterized semantic-precedence cases FAIL under current code; the request-envelope test PASSes and guards the intended exception ordering.

- [x] **Step 3: Introduce one reusable early-gate pattern in all five helpers**

  In each of `branch_draft`, `handle_draft`, `remove_draft_route`, and `remove_draft_step`, replace the first direct workspace load or pre-content no-op branch with:

  ```python
  checked = self._workspace_if_revision_matches(
      workspace_id=workspace_id,
      revision=revision,
  )
  if isinstance(checked, dict):
      return checked
  workspace = checked
  ```

  In `remove_draft_binding`, keep this envelope validation first:

  ```python
  if not inputs and not outputs:
      raise ValueError("pass at least one input or output binding to remove")
  ```

  Then insert the same early-gate block immediately after it. No other helper in this task has request-envelope validation that must remain ahead of revision preflight.

- [x] **Step 4: Simplify no-op exits to use the checked workspace**

  Replace each late `_workspace_if_revision_matches` call in no-op branches with:

  ```python
  return summarize_draft_workspace(workspace)
  ```

  Apply this to:

  - `branch_draft` when `merged == existing`;
  - `handle_draft` when `branches` is empty;
  - `handle_draft` when no patch entries were produced;
  - `remove_draft_route` when the outcome is absent;
  - `remove_draft_step` when the step is absent;
  - `remove_draft_binding` when selected bindings are absent.

  Do not add a revision increment for any no-op.

- [x] **Step 5: Run the route/removal precedence and existing no-op tests**

  Run:

  ```powershell
  uv run pytest tests/wf_api/test_drafts_service.py -q -n 0 --basetemp C:\tmp\pytest-draft-revision-route -k 'branch_draft or handle_draft or remove_draft or route_and_remove_edits_stale_revision'
  ```

  Expected: PASS, including existing no-op tests and malformed current-revision binding tests.

- [x] **Step 6: Run the complete draft service suite**

  Run:

  ```powershell
  uv run pytest tests/wf_api/test_drafts_service.py -q -n 0 --basetemp C:\tmp\pytest-draft-revision-service
  ```

  Expected: PASS with no current-revision response-shape regressions.

- [x] **Step 7: Run focused quality checks**

  Run:

  ```powershell
  uv run ruff check src/wf_api/draft_authoring.py tests/wf_api/test_drafts_service.py
  uv run ruff format --check src/wf_api/draft_authoring.py tests/wf_api/test_drafts_service.py
  uv run basedpyright src/wf_api/draft_authoring.py tests/wf_api/test_drafts_service.py --level error
  ```

  Expected: all commands exit 0.

- [x] **Step 8: Commit Task 2**

  ```powershell
  git add src/wf_api/draft_authoring.py tests/wf_api/test_drafts_service.py
  git commit -m "fix: normalize draft semantic revision precedence"
  ```

### Task 3: Cross-Layer Verification, Issue Closure, And Plan Archive

**Files:**
- Modify: `ISSUES.md`
- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-07-22-draft-semantic-revision-precedence.md`
- To: `docs/historical/superpowers/plans/2026-07-22-draft-semantic-revision-precedence.md`

**Interfaces:**
- Consumes: the unchanged public API/RPC/client/CLI contracts and corrected delegated conflict behavior from Tasks 1-2.
- Produces: verified behavior, one closed issue, one live-roadmap completion entry, and one archived implementation plan.

- [x] **Step 1: Run the relevant API/RPC/client/CLI regression suites**

  Run:

  ```powershell
  uv run pytest tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py -q -n 0 --basetemp C:\tmp\pytest-draft-revision-final
  ```

  Expected: PASS. These suites confirm that unchanged transports continue delegating the conflict envelope rather than rewriting it.

- [x] **Step 2: Run final Python quality gates**

  Run:

  ```powershell
  uv run ruff check src/wf_api src/wf_transport_rpc_http src/wf_cli tests/wf_api tests/wf_transport_rpc_http tests/wf_cli
  uv run ruff format --check src/wf_api src/wf_transport_rpc_http src/wf_cli tests/wf_api tests/wf_transport_rpc_http tests/wf_cli
  uv run basedpyright --level error
  git diff --check
  ```

  Expected: every command exits 0. Do not broaden the implementation merely to silence unrelated pre-existing findings; report any such finding before changing scope.

- [x] **Step 3: Run independent code review against the design contract**

  Use the `code-review` skill to review the Task 1-2 diff against `docs/superpowers/specs/2026-07-22-draft-semantic-revision-precedence-design.md`. Require the reviewer to check:

  - all seven listed helpers gate semantic work exactly once;
  - `remove_draft_binding` envelope validation still precedes the gate;
  - no-op branches use the already checked workspace;
  - every mutation still reaches `patch_draft_workspace` with the caller revision;
  - response shapes and public signatures are unchanged;
  - tests prove both canonical conflict and no mutation.

  Fix any Critical or Important finding, rerun the focused suite and quality gates, and commit the fix separately with a specific `fix:` message.

- [x] **Step 4: Close only the verified issue**

  Replace the `Draft revision semantics` item in `ISSUES.md` with:

  ```markdown
  ## Draft revision semantics

  - [x] Semantic draft edits consistently check the expected revision before
    reading current draft content or capability metadata. After request-envelope
    validation, stale callers receive the canonical `revision_conflict` result;
    mutation-time revision checking remains the final race-safe guard.
  ```

  Leave the data-shaping, step-metadata, and TypeScript JSON-RPC coverage items unchecked.

- [x] **Step 5: Record completion in the live roadmap**

  Add this entry beside the other completed draft-authoring work in `docs/current_roadmap.md`:

  ```markdown
  - Completed: semantic draft edits now gate workspace and capability preflight
    on the expected revision, so stale callers consistently receive
    `revision_conflict` while the patch path retains its mutation-time race
    guard. Implementation:
    [`draft semantic revision precedence`](historical/superpowers/plans/2026-07-22-draft-semantic-revision-precedence.md).
  ```

- [x] **Step 6: Archive the completed plan and update this checklist**

  Mark every completed checkbox in this plan, then run:

  ```powershell
  git mv docs/superpowers/plans/2026-07-22-draft-semantic-revision-precedence.md docs/historical/superpowers/plans/2026-07-22-draft-semantic-revision-precedence.md
  rg -n '2026-07-22-draft-semantic-revision-precedence' docs ISSUES.md
  ```

  Expected: the spec remains live under `docs/superpowers/specs/`; the roadmap points to the historical plan; no live document points to the old active-plan path.

- [x] **Step 7: Commit the verified documentation state**

  ```powershell
  git add ISSUES.md docs/current_roadmap.md docs/superpowers/plans/2026-07-22-draft-semantic-revision-precedence.md docs/historical/superpowers/plans/2026-07-22-draft-semantic-revision-precedence.md
  git commit -m "docs: complete draft revision precedence"
  ```

- [x] **Step 8: Confirm final repository state**

  Run:

  ```powershell
  git status --short
  git log -3 --oneline
  ```

  Expected: no tracked changes remain. The ACL-protected `pytest-of-lda/` directory may remain untracked and must not be staged.
