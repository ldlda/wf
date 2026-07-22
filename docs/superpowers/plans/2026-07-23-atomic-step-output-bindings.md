# Atomic Step Output Bindings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one revision-checked operation that atomically replaces a capability step's ordered canonical output bindings while projecting missing workflow state schemas.

**Architecture:** Reuse the core `OutputBinding` model from API through transport. Put capability-aware source validation and state-schema projection in `WorkflowDraftAuthoringApi`, use the existing `wf_api.schema_projection` helpers, and retain the map operation only as a compatibility adapter. The CLI lowers ordered flags or a canonical JSON file into the same binding list.

**Tech Stack:** Python 3.14, Pydantic 2, JSON Schema Draft 2020-12, Typer, FastAPI JSON-RPC, FastMCP, pytest, Ruff, basedpyright.

## Global Constraints

- Do not add another output-binding model or mapping language.
- Preserve canonical binding order and permit one local source to feed several distinct state targets.
- Reject duplicate and ancestor/descendant state targets before mutation.
- Validate local sources against the selected capability output schema.
- Project missing state target schemas atomically; never delete state schema when replacing or clearing bindings.
- Accept an existing target schema only when it is exactly equal to the selected source fragment.
- Envelope validation precedes revision checking; stale revision then precedes workspace, capability, and schema semantics.
- Changed replacements advance exactly one revision; exact replacements are revision-checked no-ops.
- Keep the legacy map API/RPC and `--merge` behavior operational for real callers and label it compatibility-only and lossy.
- Do not change workflow-output bindings, runtime binding models, TypeScript RPC, or revision history.
- Add comments around whole-payload projection, monotonic state-schema projection, and CLI compatibility dispatch.

---

### Task 1: Atomic Capability-Aware Output Replacement

**Files:**
- Modify: `src/wf_api/draft_authoring.py`
- Modify: `src/wf_api/surface.py`
- Modify: `src/wf_api/service.py`
- Test: `tests/wf_api/test_drafts_service.py`
- Test: `tests/core/test_atomic_state_patches.py`

**Interfaces:**
- Consumes: `OutputBinding`, `schema_fragment_at_path`, `schema_path_exists`, `project_schema_path_to_schema_path`, `WorkflowDraftAuthoringApi._workspace_if_revision_matches`, and `WorkflowDraftApi.patch_draft_workspace`.
- Produces:

  ```python
  async def set_step_output_bindings(
      *,
      workspace_id: str,
      revision: int,
      step_id: str,
      bindings: Sequence[OutputBinding],
  ) -> dict[str, Any]: ...
  ```

- Preserves: `set_step_output_map(..., merge=...)` unchanged as a compatibility operation.

- [ ] **Step 1: Write failing canonical replacement and fan-out tests**

  Add tests alongside the canonical input-binding tests. Use an existing test
  capability whose output schema contains a nested object, or register one with
  an output contract equivalent to:

  ```python
  {
      "type": "object",
      "properties": {
          "report": {
              "type": "object",
              "properties": {
                  "title": {"type": "string"},
                  "markdown": {"type": "string"},
              },
              "required": ["title", "markdown"],
          }
      },
      "required": ["report"],
  }
  ```

  Pin exact stored order and source fan-out:

  ```python
  result = await api.set_step_output_bindings(
      workspace_id="draft-output-bindings",
      revision=1,
      step_id="analyze",
      bindings=[
          OutputBinding(
              source=LocalPath.parse("report.title"),
              target=StatePath.parse("state.report.title"),
          ),
          OutputBinding(
              source=LocalPath.parse("report.title"),
              target=StatePath.parse("state.audit.title"),
          ),
      ],
  )

  assert result["revision"] == 2
  inspected = await api.get_draft_workspace(
      workspace_id="draft-output-bindings",
      include_draft=True,
  )
  assert inspected["draft"]["steps"]["analyze"]["output"] == [
      {"source": "report.title", "target": "state.report.title"},
      {"source": "report.title", "target": "state.audit.title"},
  ]
  ```

- [ ] **Step 2: Write failing schema projection tests**

  Cover nested source-to-target projection, whole-payload `.` projection,
  exact-equivalent existing target acceptance, and incompatible existing target
  rejection. Assert projected fields rather than whole schema equality:

  ```python
  state_schema = inspected["draft"]["state_schema"]
  assert state_schema["properties"]["report"]["properties"]["title"] == {
      "type": "string"
  }
  assert state_schema["properties"]["audit"]["properties"]["title"] == {
      "type": "string"
  }
  ```

  For whole payload:

  ```python
  bindings=[
      OutputBinding(
          source=LocalPath.root(),
          target=StatePath.parse("state.raw_result"),
      )
  ]
  ```

  Verify the complete capability output object appears below
  `state_schema.properties.raw_result`.

- [ ] **Step 3: Write failing semantic-error and revision tests**

  Add cases for:

  - missing local source;
  - duplicate state target;
  - `state.report` overlapping `state.report.title`;
  - incompatible existing state target schema;
  - missing or non-capability step;
  - stale revision combined with each semantic error class;
  - unchanged draft and revision after every failure;
  - exact replacement returning a no-op summary at the current revision;
  - `bindings=[]` clearing outputs without deleting projected state fields.

  Error assertions should include stable binding indexes:

  ```python
  with pytest.raises(
      ValueError,
      match=r"bindings\[0\]\.target 'state\.report' overlaps "
      r"bindings\[1\]\.target 'state\.report\.title'",
  ):
      await api.set_step_output_bindings(...)
  ```

- [ ] **Step 4: Run focused API tests and confirm RED**

  Run:

  ```bash
  uv run pytest tests/wf_api/test_drafts_service.py -q -k "step_output"
  ```

  Expected: failures because `WorkflowApi.set_step_output_bindings` does not
  exist.

- [ ] **Step 5: Add output overlap and patch helpers**

  In `src/wf_api/draft_authoring.py`, add focused helpers beside the input
  equivalents:

  ```python
  def _overlapping_output_targets_error(
      bindings: Sequence[OutputBinding],
  ) -> ValueError:
      """Describe the first overlapping state-target pair with stable indexes."""
      for left_index, left in enumerate(bindings):
          for right_index in range(left_index + 1, len(bindings)):
              right = bindings[right_index]
              if paths_overlap(str(left.target), str(right.target)):
                  return ValueError(
                      f"bindings[{left_index}].target {str(left.target)!r} "
                      f"overlaps bindings[{right_index}].target "
                      f"{str(right.target)!r}"
                  )
      raise AssertionError("overlap error requested without overlapping targets")


  def _step_output_bindings_patch(
      *,
      workspace: WorkflowDraftWorkspace,
      step_id: str,
      bindings: list[dict[str, Any]],
      state_schema: dict[str, Any],
  ) -> list[dict[str, Any]]:
      """Build one atomic patch for state schema and canonical step outputs."""
      patch: list[dict[str, Any]] = []
      if workspace.draft.get("state_schema", {}) != state_schema:
          patch.append(
              {"op": "replace", "path": "/state_schema", "value": state_schema}
          )
      patch.append(
          {
              "op": "replace",
              "path": f"/steps/{escape_json_pointer(step_id)}/output",
              "value": bindings,
          }
      )
      return patch
  ```

  `paths_overlap` operates on rootless path syntax, so passing both serialized
  `state.*` values gives it a shared synthetic root and preserves equality and
  ancestry checks. Keep this comment at the helper call because the type seam
  is otherwise non-obvious.

- [ ] **Step 6: Implement canonical output replacement**

  Add `WorkflowDraftAuthoringApi.set_step_output_bindings`:

  ```python
  async def set_step_output_bindings(
      self,
      *,
      workspace_id: str,
      revision: int,
      step_id: str,
      bindings: Sequence[OutputBinding],
  ) -> dict[str, Any]:
      """Replace one capability step's canonical output bindings atomically."""
      checked = self._workspace_if_revision_matches(
          workspace_id=workspace_id,
          revision=revision,
      )
      if isinstance(checked, dict):
          return checked
      workspace = checked
      step = draft_step(workspace.draft, step_id)
      capability_name = step.get("use")
      if not isinstance(capability_name, str) or not capability_name:
          raise ValueError(
              f"draft step {step_id!r} does not declare a capability use"
          )
      spec = self.context.specs.get_qualified_spec(capability_name)
      capability_schema = (
          spec.output_schema_contract or spec.output_model.model_json_schema()
      )

      targets = [str(binding.target) for binding in bindings]
      if has_overlapping_paths(targets):
          raise _overlapping_output_targets_error(bindings)

      projected_state = _draft_schema(workspace.draft, "state_schema")
      for index, binding in enumerate(bindings):
          source_parts = binding.source.parts
          try:
              schema_fragment_at_path(
                  capability_schema,
                  source_parts,
                  label="capability output schema",
              )
          except ValueError as exc:
              raise ValueError(
                  f"bindings[{index}].source {str(binding.source)!r} "
                  f"is not declared by capability {capability_name!r}: {exc}"
              ) from exc

          target_parts = binding.target.parts
          try:
              projected_state = project_schema_path_to_schema_path(
                  target_schema=projected_state,
                  source_schema=capability_schema,
                  source_parts=source_parts,
                  target_parts=target_parts,
                  allow_existing_equivalent=True,
              )
          except ValueError as exc:
              raise ValueError(
                  f"bindings[{index}].target {str(binding.target)!r} "
                  f"cannot receive source {str(binding.source)!r}: {exc}"
              ) from exc

      payload = [binding.model_dump(mode="json") for binding in bindings]
      if (
          step.get("output", []) == payload
          and workspace.draft.get("state_schema", {}) == projected_state
      ):
          return summarize_draft_workspace(workspace)

      return await self.drafts.patch_draft_workspace(
          workspace_id=workspace_id,
          revision=revision,
          patch=_step_output_bindings_patch(
              workspace=workspace,
              step_id=step_id,
              bindings=payload,
              state_schema=projected_state,
          ),
      )
  ```

  The unconditional projection call naturally inserts missing targets and
  accepts only exact existing targets. Wrap its errors with the binding index,
  target, and source so incompatible-schema diagnostics satisfy the public
  error contract.

- [ ] **Step 7: Expose the operation through the API protocol and service**

  Add the same `Sequence[OutputBinding]` signature to `WorkflowApiSurface` and
  delegate from `WorkflowApi` to `self.draft_authoring` exactly as the canonical
  input operation does.

- [ ] **Step 8: Add compile-and-run fan-out coverage**

  In `tests/core/test_atomic_state_patches.py`, add a focused
  `apply_output_bindings` regression where one local source is bound to two
  state targets. Assert both state values after application. The authoring API
  test separately proves the same canonical list compiles. Do not only inspect
  serialized draft JSON.

- [ ] **Step 9: Run API and runtime tests**

  Run:

  ```bash
  uv run pytest tests/wf_api/test_drafts_service.py tests/core/test_atomic_state_patches.py -q
  ```

  Expected: PASS.

- [ ] **Step 10: Commit Task 1**

  ```bash
  git add src/wf_api/draft_authoring.py src/wf_api/surface.py src/wf_api/service.py tests/wf_api/test_drafts_service.py tests/core/test_atomic_state_patches.py
  git commit -m "feat: replace draft step output bindings"
  ```

---

### Task 2: JSON-RPC Model, Method, And Remote Client

**Files:**
- Modify: `src/wf_transport_rpc_http/models.py`
- Modify: `src/wf_transport_rpc_http/__init__.py`
- Modify: `src/wf_transport_rpc_http/methods/drafts.py`
- Modify: `src/wf_transport_rpc_http/client/drafts.py`
- Test: `tests/wf_transport_rpc_http/test_app.py`
- Test: `tests/wf_transport_rpc_http/test_client.py`

**Interfaces:**
- Consumes: Task 1 `WorkflowApi.set_step_output_bindings` and core `OutputBinding`.
- Produces:

  ```python
  class SetStepOutputBindingsParams(RpcParamsModel):
      workspace_id: str
      revision: int
      step_id: str
      bindings: list[OutputBinding]
  ```

  and remote client method `set_step_output_bindings(...)`.

- [ ] **Step 1: Write failing RPC application tests**

  Add a request containing duplicate sources and ordered distinct targets:

  ```python
  response = await _rpc(
      app,
      "workflow.draft_workspaces.set_step_output_bindings",
      {
          "workspace_id": "draft-rpc-output-bindings",
          "revision": 1,
          "step_id": "analyze",
          "bindings": [
              {"source": "report.title", "target": "state.report.title"},
              {"source": "report.title", "target": "state.audit.title"},
          ],
      },
  )
  ```

  Inspect the workspace and assert exact list order. Add malformed requests for
  missing `source`, bare state target, unexpected fields, and invalid root
  marker. These must return JSON-RPC invalid-params errors without invoking the
  semantic method.

- [ ] **Step 2: Write failing remote client tests**

  Call the typed client with two `OutputBinding` values sharing a source. Assert
  the recorded wire method and JSON payload exactly:

  ```python
  assert call["method"] == (
      "workflow.draft_workspaces.set_step_output_bindings"
  )
  assert call["params"]["bindings"] == [
      {"source": "report.title", "target": "state.report.title"},
      {"source": "report.title", "target": "state.audit.title"},
  ]
  ```

- [ ] **Step 3: Run RPC tests and confirm RED**

  ```bash
  uv run pytest tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py -q -k "step_output"
  ```

  Expected: unknown method/model/client failures.

- [ ] **Step 4: Add the typed parameter model and exports**

  Import `OutputBinding` in `models.py`, define
  `SetStepOutputBindingsParams`, and add it to `wf_transport_rpc_http.__init__`
  imports and `__all__`.

- [ ] **Step 5: Register the JSON-RPC method**

  In `methods/drafts.py`, register:

  ```python
  @method(
      name="workflow.draft_workspaces.set_step_output_bindings",
      params_model=SetStepOutputBindingsParams,
  )
  async def workflow_draft_workspaces_set_step_output_bindings(
      params: SetStepOutputBindingsParams = RpcParams(),
  ) -> dict[str, Any]:
      return await server.api.set_step_output_bindings(
          workspace_id=params.workspace_id,
          revision=params.revision,
          step_id=params.step_id,
          bindings=params.bindings,
      )
  ```

  Follow the existing decorator signature exactly if it differs from this
  abbreviated example.

- [ ] **Step 6: Add the remote client method**

  Mirror `set_step_input_bindings` and serialize each binding with
  `model_dump(mode="json")`. Do not lower through `output_map`.

- [ ] **Step 7: Run RPC tests**

  ```bash
  uv run pytest tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py -q
  ```

  Expected: PASS.

- [ ] **Step 8: Commit Task 2**

  ```bash
  git add src/wf_transport_rpc_http tests/wf_transport_rpc_http
  git commit -m "feat: expose output bindings over rpc"
  ```

---

### Task 3: MCP Canonical Output Tool

**Files:**
- Modify: `src/wf_mcp/workflow_surface/models.py`
- Modify: `src/wf_mcp/workflow_surface/tools.py`
- Modify: `src/wf_mcp/proxy/runtime.py`
- Test: `tests/wf_mcp/workflow_surface/test_drafts.py`
- Test: `tests/wf_mcp/server/test_tools.py`
- Test: `tests/wf_mcp/server/test_config.py`

**Interfaces:**
- Consumes: Task 1 `WorkflowApiSurface.set_step_output_bindings` and core `OutputBinding`.
- Produces:

  ```python
  class SetStepOutputBindingsRequest(BaseModel):
      workspace_id: WorkspaceId
      revision: int
      step_id: NonEmptyString
      bindings: DraftOutputBindings
  ```

  and MCP tool `wf.workflow.set_step_output_bindings`.

- [ ] **Step 1: Write failing request-model tests**

  Validate ordered fan-out and reject malformed canonical records:

  ```python
  request = SetStepOutputBindingsRequest.model_validate(
      {
          "workspace_id": "draft-output",
          "revision": 4,
          "step_id": "analyze",
          "bindings": [
              {"source": "report.title", "target": "state.report.title"},
              {"source": "report.title", "target": "state.audit.title"},
          ],
      }
  )

  assert [str(binding.source) for binding in request.bindings] == [
      "report.title",
      "report.title",
  ]
  ```

- [ ] **Step 2: Write failing handler and discovery tests**

  Use the workflow-surface handler fake to assert the tool delegates once with
  typed bindings in order. Add the tool name to server discovery/config tests
  and the always-visible proxy list assertion.

- [ ] **Step 3: Run focused MCP tests and confirm RED**

  ```bash
  uv run pytest tests/wf_mcp/workflow_surface/test_drafts.py tests/wf_mcp/server/test_tools.py tests/wf_mcp/server/test_config.py -q -k "output_bindings or tools or config"
  ```

- [ ] **Step 4: Add the MCP request model**

  Define `SetStepOutputBindingsRequest` beside the map request and describe it
  as complete ordered replacement. Reuse `DraftOutputBindings`; do not define a
  second union or path-map type.

- [ ] **Step 5: Register the MCP tool**

  Add:

  ```python
  @mcp.tool(
      name="wf.workflow.set_step_output_bindings",
      description=(
          "Replace one capability step's complete ordered output bindings. "
          "Repeated sources are valid fan-out; state targets must not overlap."
      ),
  )
  async def set_step_output_bindings(
      request: SetStepOutputBindingsRequest,
  ) -> dict[str, Any]:
      return dict(
          await handlers.set_step_output_bindings(
              workspace_id=request.workspace_id,
              revision=request.revision,
              step_id=request.step_id,
              bindings=request.bindings,
          )
      )
  ```

  Follow local registration and result-conversion conventions exactly.

- [ ] **Step 6: Pin the tool in proxy discovery**

  Add `wf.workflow.set_step_output_bindings` beside input bindings in
  `_SEARCH_ALWAYS_VISIBLE_TOOL_NAMES`.

- [ ] **Step 7: Run MCP tests**

  ```bash
  uv run pytest tests/wf_mcp/workflow_surface/test_drafts.py tests/wf_mcp/server/test_tools.py tests/wf_mcp/server/test_config.py -q
  ```

  Expected: PASS.

- [ ] **Step 8: Commit Task 3**

  ```bash
  git add src/wf_mcp tests/wf_mcp
  git commit -m "feat: expose canonical output bindings to mcp"
  ```

---

### Task 4: Typer Replacement Modes And Remote CLI

**Files:**
- Modify: `src/wf_cli/commands/draft_options.py`
- Modify: `src/wf_cli/commands/drafts.py`
- Test: `tests/wf_cli/test_app.py`
- Test: `tests/wf_cli/test_remote_target.py`

**Interfaces:**
- Consumes: core `OutputBinding`, Task 1 local API operation, and Task 2 remote client method.
- Produces:

  ```python
  def parse_step_output_binding_flags(
      values: list[str] | None,
  ) -> list[OutputBinding]: ...

  def parse_step_output_bindings_file(path: Path) -> list[OutputBinding]: ...
  ```

- Keeps: `wf draft set-output`; no new command name.

- [ ] **Step 1: Write failing parser tests**

  Add tests proving repeated sources remain separate and file order is exact:

  ```python
  bindings = parse_step_output_binding_flags(
      [
          "report.title=state.report.title",
          "report.title=state.audit.title",
      ]
  )
  assert [binding.model_dump(mode="json") for binding in bindings] == [
      {"source": "report.title", "target": "state.report.title"},
      {"source": "report.title", "target": "state.audit.title"},
  ]
  ```

  File tests must reject a JSON object, missing fields, unexpected fields,
  invalid local source syntax, and non-state targets as concise
  `typer.BadParameter` errors.

- [ ] **Step 2: Write failing local command tests**

  Cover:

  - repeated `--map` canonical replacement;
  - `--bindings-file` replacement;
  - explicit `--clear`;
  - no mode selected;
  - `--bindings-file` or `--clear` combined with `--map`;
  - `--merge` combined with file/clear;
  - `--merge --map` dispatching to `set_step_output_map` only;
  - duplicate-source fan-out dispatching to `set_step_output_bindings` only.

- [ ] **Step 3: Write failing remote-target tests**

  Run the same repeated-source and file modes with `--target`. Assert the RPC
  method is exactly
  `workflow.draft_workspaces.set_step_output_bindings`, called once, with list
  order preserved. Retain one compatibility `--merge` assertion for
  `set_step_output_map`.

- [ ] **Step 4: Run focused CLI tests and confirm RED**

  ```bash
  uv run pytest tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py -q -k "set_output"
  ```

- [ ] **Step 5: Add output binding parsers**

  In `draft_options.py`, import `OutputBinding`, add a
  `TypeAdapter(list[OutputBinding])`, parse ordered flags directly rather than
  through `_parse_assignment_flags`, and translate Pydantic/path failures with
  `validation_error_as_bad_parameter`:

  ```python
  def parse_step_output_binding_flags(
      values: list[str] | None,
  ) -> list[OutputBinding]:
      """Parse ordered local-to-state outputs without collapsing fan-out."""
      bindings: list[OutputBinding] = []
      for item in values or []:
          source, separator, target = item.partition("=")
          if separator != "=" or not source or not target:
              raise typer.BadParameter(
                  "--map must use LOCAL_SOURCE=STATE_TARGET"
              )
          try:
              bindings.append(
                  OutputBinding(
                      source=LocalPath.parse(source),
                      target=StatePath.parse(target),
                  )
              )
          except (PathResolutionError, ValidationError) as exc:
              raise typer.BadParameter(str(exc)) from exc
      return bindings
  ```

  `parse_step_output_bindings_file` validates `parse_json_file(...)` through the
  adapter exactly as the input file parser does.

- [ ] **Step 6: Rework `wf draft set-output` dispatch**

  Add `--bindings-file: Path | None` and `--clear: bool`. Use this mode matrix:

  ```python
  has_maps = bool(mapping)
  has_file = bindings_file is not None
  selected_modes = sum((has_maps, has_file, clear))
  if selected_modes == 0:
      raise typer.BadParameter("provide --map, --bindings-file, or --clear")
  if selected_modes > 1:
      raise typer.BadParameter(
          "--bindings-file and --clear cannot be combined with --map"
      )
  if merge and (has_file or clear):
      raise typer.BadParameter(
          "--merge is supported only for compatibility map-only edits"
      )
  ```

  Dispatch `--merge --map` through `_parse_output_map_flags` and
  `set_step_output_map`. Dispatch every replacement mode through canonical
  bindings and `set_step_output_bindings`. The no-flags case must no longer
  silently clear outputs; clearing requires `--clear`.

- [ ] **Step 7: Update command help tests**

  Pin direction and semantics:

  ```text
  --map LOCAL_SOURCE=STATE_TARGET
  --bindings-file ordered canonical JSON array
  --clear replace with no bindings
  --merge compatibility-only and potentially lossy
  ```

- [ ] **Step 8: Run CLI tests**

  ```bash
  uv run pytest tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py -q
  ```

  Expected: PASS.

- [ ] **Step 9: Commit Task 4**

  ```bash
  git add src/wf_cli tests/wf_cli
  git commit -m "feat: replace draft output bindings from cli"
  ```

---

### Task 5: Documentation, Issue State, Review, And Final Verification

**Files:**
- Modify: `ISSUES.md`
- Modify: `skills/wf-cli/SKILL.md`
- Modify: `skills/wf-workflow/references/draft-workspaces.md`
- Modify: `skills/wf-workflow/references/workflow-lifecycle.md`
- Modify: `docs/workflow_capabilities.md`
- Modify: `docs/wf_mcp_operator_manual.md`
- Modify: `docs/current_roadmap.md`
- Move after completion: `docs/superpowers/plans/2026-07-23-atomic-step-output-bindings.md` to `docs/historical/superpowers/plans/2026-07-23-atomic-step-output-bindings.md`

**Interfaces:**
- Consumes: all completed implementation tasks and their verified command names.
- Produces: current user/agent guidance, accurate issue state, archived checked plan, and a final verification report.

- [ ] **Step 1: Update issue language without falsely closing map loss**

  Keep the combined issue unchecked and revise it to state:

  ```markdown
  - [ ] Compatibility step input/output maps can still collapse valid canonical
    fan-out bindings. Canonical input and output replacement preserve ordered
    fan-out, but later compatibility-map merges remain inherently lossy.
  ```

  Leave workflow-output literals, nested workflow-output projection, focused
  step updates, and TypeScript parity unchecked.

- [ ] **Step 2: Update CLI and agent documentation**

  Replace descriptions that say `set-output` replaces a map with canonical-list
  language. Include examples for repeated-source fan-out, file round-trip,
  explicit clear, and compatibility merge:

  ```bash
  wf draft set-output WS --revision 4 --step analyze \
    --map report.title=state.report.title \
    --map report.title=state.audit.title

  wf draft inspect WS --include-draft |
    jq '.draft.steps.analyze.output' > output-bindings.json

  wf draft set-output WS --revision 5 --step analyze \
    --bindings-file output-bindings.json

  wf draft set-output WS --revision 6 --step analyze --clear
  ```

  Explicitly warn that `--merge --map` is compatibility-only and may collapse
  existing fan-out.

- [ ] **Step 3: Update RPC/MCP operation inventories**

  Add `workflow.draft_workspaces.set_step_output_bindings` and
  `wf.workflow.set_step_output_bindings` to user-facing inventories and examples
  near their input counterparts.

- [ ] **Step 4: Run focused matrix verification**

  ```bash
  uv run pytest \
    tests/wf_api/test_drafts_service.py \
    tests/wf_transport_rpc_http/test_app.py \
    tests/wf_transport_rpc_http/test_client.py \
    tests/wf_mcp/workflow_surface/test_drafts.py \
    tests/wf_mcp/server/test_tools.py \
    tests/wf_mcp/server/test_config.py \
    tests/wf_cli/test_app.py \
    tests/wf_cli/test_remote_target.py \
    -q
  ```

  Expected: PASS with only already-known dependency deprecation warnings.

- [ ] **Step 5: Run static verification**

  ```bash
  uv run ruff check
  uv run ruff format --check
  uv run basedpyright --level error
  git diff --check
  ```

  Expected: all clean.

- [ ] **Step 6: Run independent review**

  Use the repository code-review skill against the pre-slice commit. Fix every
  Critical or Important finding. Record Minor deferrals with concrete reasons
  in the final report.

- [ ] **Step 7: Update roadmap and archive this plan**

  Add a completed roadmap entry linking to:

  ```text
  historical/superpowers/plans/2026-07-23-atomic-step-output-bindings.md
  ```

  Check every completed plan box, move the plan under `docs/historical/`, and
  verify no live link still points to its old location.

- [ ] **Step 8: Commit documentation and completion state**

  ```bash
  git add ISSUES.md skills docs
  git commit -m "docs: complete atomic step output bindings"
  ```

- [ ] **Step 9: Final repository check**

  ```bash
  git status --short
  git log -7 --oneline
  ```

  Expected: clean worktree and one coherent commit per task plus any explicitly
  identified review-fix commit.

## Plan Self-Review

- The plan implements every approved spec surface: Python API, RPC, MCP, CLI,
  compatibility behavior, docs, and issue state.
- The canonical model stays `OutputBinding`; no map or new union appears on the
  replacement path.
- State schema projection uses the existing shared helper and is monotonic.
- Fan-out is tested at serialization and runtime boundaries.
- Revision precedence, no-op behavior, clear behavior, and no-mutation failures
  are explicit.
- Workflow-output authoring, focused step updates, and TypeScript parity remain
  separate slices.
