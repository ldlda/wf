# Atomic Step Input Bindings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one revision-checked operation that atomically replaces a capability step's canonical input-binding list, including nested graph-path fan-out and literal JSON values.

**Architecture:** Reuse the existing `InputPathBinding | InputValueBinding` core model from API through transport. Put capability-aware target validation and input/state schema projection in `WorkflowDraftAuthoringApi`, keep JSON Schema traversal in `wf_api.schema_projection`, and retain the old map operation only as a compatibility adapter. The CLI lowers either repeatable convenience flags or a canonical JSON file into the same binding list.

**Tech Stack:** Python 3.14, Pydantic 2, JSON Schema Draft 2020-12, Typer, FastAPI JSON-RPC, FastMCP, pytest, Ruff, basedpyright.

## Global Constraints

- Do not add a persisted `CompositeBinding` or any second binding language.
- Preserve canonical binding order and permit one source to feed several distinct targets.
- Reject duplicate and ancestor/descendant local targets before mutation.
- Validate literals against the selected capability-input subschema.
- Project missing `input.*` and `state.*` schemas atomically; never project `context.*`.
- Envelope validation precedes revision checking; stale revision then precedes workspace/catalog semantics.
- Changed replacements advance exactly one revision; exact replacements are revision-checked no-ops.
- Keep the legacy map-only API/RPC and `--merge` behavior operational for real callers.
- Do not change step outputs, workflow outputs, revision history, TypeScript RPC, or runtime binding models.
- Add docstrings/comments around whole-payload projection, schema-reference preservation, and CLI compatibility dispatch.

---

### Task 1: Shared Schema Fragment Selection And Literal Validation

**Files:**
- Modify: `src/wf_api/schema_projection.py`
- Test: `tests/wf_api/test_schema_projection.py`

**Interfaces:**
- Consumes: existing `_schema_at_path`, `_resolve_local_reference`, and definition merge helpers.
- Produces:

  ```python
  def schema_fragment_at_path(
      schema: JsonObject,
      parts: Sequence[str],
      *,
      label: str = "schema",
  ) -> JsonObject: ...

  def validate_json_value_at_schema_path(
      *,
      schema: JsonObject,
      parts: Sequence[str],
      value: object,
      label: str,
  ) -> None: ...
  ```

- Extends: `project_schema_path_to_schema_path` accepts an empty `source_parts` tuple to project the complete source schema for whole-payload target `.`.

- [ ] **Step 1: Write failing schema-fragment tests**

  Add tests covering an inline nested field, a selected `$ref` leaf that needs
  root `$defs`, the root fragment for `parts=()`, and a remote selected ref:

  ```python
  def test_schema_fragment_preserves_defs_for_selected_reference() -> None:
      fragment = schema_fragment_at_path(
          {
              "type": "object",
              "properties": {"request": {"$ref": "#/$defs/Request"}},
              "$defs": {
                  "Request": {
                      "type": "object",
                      "properties": {"format": {"type": "string"}},
                  }
              },
          },
          ("request",),
          label="capability input schema",
      )

      assert fragment["$ref"] == "#/$defs/Request"
      assert fragment["$defs"]["Request"]["properties"]["format"] == {
          "type": "string"
      }
  ```

  ```python
  def test_schema_fragment_accepts_whole_schema() -> None:
      schema = {"type": "object", "properties": {"title": {"type": "string"}}}

      assert schema_fragment_at_path(schema, ()) == schema
  ```

- [ ] **Step 2: Write failing literal-validation tests**

  Pin valid/invalid strings, objects, arrays, and `null`, including a selected
  schema behind a local reference:

  ```python
  def test_validate_json_value_at_nested_schema_path() -> None:
      schema = {
          "type": "object",
          "properties": {"request": {"$ref": "#/$defs/Request"}},
          "$defs": {
              "Request": {
                  "type": "object",
                  "properties": {"format": {"enum": ["markdown", "json"]}},
              }
          },
      }

      validate_json_value_at_schema_path(
          schema=schema,
          parts=("request", "format"),
          value="markdown",
          label="bindings[0].value",
      )

      with pytest.raises(
          ValueError,
          match=r"bindings\[0\]\.value does not satisfy schema at 'request.format'",
      ):
          validate_json_value_at_schema_path(
              schema=schema,
              parts=("request", "format"),
              value="html",
              label="bindings[0].value",
          )
  ```

- [ ] **Step 3: Write a failing whole-schema projection test**

  ```python
  def test_project_schema_path_accepts_whole_source_schema() -> None:
      projected = project_schema_path_to_schema_path(
          target_schema={"type": "object", "properties": {}},
          source_schema={
              "type": "object",
              "properties": {"title": {"type": "string"}},
              "required": ["title"],
          },
          source_parts=(),
          target_parts=("payload",),
      )

      assert projected["properties"]["payload"]["required"] == ["title"]
  ```

- [ ] **Step 4: Run the focused tests and confirm RED**

  Run:

  ```bash
  uv run pytest tests/wf_api/test_schema_projection.py -q
  ```

  Expected: failures because the two public helpers do not exist and whole
  source projection rejects an empty source path.

- [ ] **Step 5: Implement fragment selection and literal validation**

  Import JSON Schema's instance-validation error separately from schema errors,
  then add:

  ```python
  from jsonschema import Draft202012Validator, SchemaError, ValidationError


  def schema_fragment_at_path(
      schema: JsonObject,
      parts: Sequence[str],
      *,
      label: str = "schema",
  ) -> JsonObject:
      """Return a self-contained selected schema fragment with local defs."""
      _check_schema(label, schema)
      fragment = deepcopy(_schema_at_path(schema, parts, label=label))
      _merge_definition_block(
          fragment,
          schema,
          "$defs",
          target_label=f"{label} fragment",
          source_label=label,
      )
      _merge_definition_block(
          fragment,
          schema,
          "definitions",
          target_label=f"{label} fragment",
          source_label=label,
      )
      _check_schema(f"{label} fragment", fragment)
      return fragment


  def validate_json_value_at_schema_path(
      *,
      schema: JsonObject,
      parts: Sequence[str],
      value: object,
      label: str,
  ) -> None:
      """Validate one known literal against a selected schema path."""
      fragment = schema_fragment_at_path(schema, parts, label="capability input schema")
      path = ".".join(parts) or "."
      try:
          Draft202012Validator(fragment).validate(value)
      except ValidationError as exc:
          raise ValueError(
              f"{label} does not satisfy schema at {path!r}: {exc.message}"
          ) from exc
  ```

  In `project_schema_path_to_schema_path`, replace the empty-source rejection
  with root selection:

  ```python
  source_value = (
      source_schema
      if not source_parts
      else _schema_at_path(source_schema, source_parts, label="source schema")
  )
  ```

  Keep the existing empty-target rejection. Deep-copy `source_value` and merge
  definition blocks exactly as today. Extend `_merge_definition_block` with
  keyword-only `source_label` and `target_label` parameters whose defaults
  preserve current projection error wording; fragment selection passes the
  capability-schema labels shown above.

  ```python
  def _merge_definition_block(
      target_schema: JsonObject,
      source_schema: JsonObject,
      key: str,
      *,
      target_label: str = "state_schema",
      source_label: str = "output_schema",
  ) -> None:
      source_defs = source_schema.get(key)
      if source_defs is None:
          return
      if not isinstance(source_defs, dict):
          raise ValueError(f"{source_label}.{key} must be an object")
      target_defs = target_schema.setdefault(key, {})
      if not isinstance(target_defs, dict):
          raise ValueError(f"{target_label}.{key} must be an object")
      for name, definition in source_defs.items():
          if name in target_defs and target_defs[name] != definition:
              raise ValueError(f"conflicting {key}.{name}")
          target_defs[name] = deepcopy(definition)
  ```

- [ ] **Step 6: Run focused tests and quality checks**

  Run:

  ```bash
  uv run pytest tests/wf_api/test_schema_projection.py -q
  uv run ruff check src/wf_api/schema_projection.py tests/wf_api/test_schema_projection.py
  uv run ruff format --check src/wf_api/schema_projection.py tests/wf_api/test_schema_projection.py
  uv run basedpyright --level error src/wf_api/schema_projection.py
  ```

  Expected: all pass with no diagnostics.

- [ ] **Step 7: Commit Task 1**

  ```bash
  git add src/wf_api/schema_projection.py tests/wf_api/test_schema_projection.py
  git commit -m "feat: validate values at schema paths"
  ```

---

### Task 2: Atomic Capability-Aware Input Replacement

**Files:**
- Modify: `src/wf_api/draft_authoring.py`
- Modify: `src/wf_api/surface.py`
- Modify: `src/wf_api/service.py`
- Test: `tests/wf_api/test_drafts_service.py`

**Interfaces:**
- Consumes: `schema_fragment_at_path`, `validate_json_value_at_schema_path`, `project_schema_path_to_schema_path`, `has_overlapping_paths`, canonical `InputBinding` models.
- Produces: `WorkflowApiSurface.set_step_input_bindings(...)` with the exact signature from the design spec.

- [ ] **Step 1: Write failing structured-assembly and fan-out API tests**

  Reuse the nested report capability fixture from the preceding nested-binding
  slice. Add one test that replaces a step input list with two nested path
  bindings and one literal, then inspects canonical order:

  ```python
  result = await api.set_step_input_bindings(
      workspace_id="structured_input",
      revision=1,
      step_id="report",
      bindings=[
          InputPathBinding(
              path=GraphSourcePath.state("report", "title"),
              target=LocalPath.of("request", "title"),
          ),
          InputPathBinding(
              path=GraphSourcePath.state("report", "markdown"),
              target=LocalPath.of("request", "body"),
          ),
          InputValueBinding(
              target=LocalPath.of("request", "format"),
              value="markdown",
          ),
      ],
  )

  assert result["revision"] == 2
  assert inspected["draft"]["steps"]["report"]["input"] == [
      {"target": "request.title", "path": "state.report.title"},
      {"target": "request.body", "path": "state.report.markdown"},
      {"target": "request.format", "value": "markdown"},
  ]
  ```

  Add a separate fan-out assertion using the same `state.report.title` source
  for `request.title` and `audit.title`.

- [ ] **Step 2: Write failing semantic-error and no-mutation tests**

  Add parameterized tests for missing target, duplicate target,
  ancestor/descendant overlap, invalid literal, unsupported remote target ref,
  and non-capability step. Snapshot the workspace before each call and assert it
  is byte-for-byte unchanged afterward.

  Add stale-revision cases paired with missing target and invalid literal; both
  must return `revision_conflict` before those semantic errors.

- [ ] **Step 3: Write failing projection, whole-payload, context, and no-op tests**

  Cover:

  ```python
  bindings=[
      InputPathBinding(path="input.payload", target="."),
  ]
  ```

  with a missing `input.payload` schema projected from the complete capability
  input schema. Add input/state multi-projection, a `context.prior_outcome`
  binding that changes no workflow schema, explicit valid `null`, and an exact
  second replacement that leaves the revision unchanged.

- [ ] **Step 4: Run API tests and confirm RED**

  Run:

  ```bash
  uv run pytest tests/wf_api/test_drafts_service.py -k "step_input_bindings" -q
  ```

  Expected: failures because the surface and implementation method do not exist.

- [ ] **Step 5: Implement the semantic operation**

  Add imports for `InputPathBinding`, `InputValueBinding`,
  `has_overlapping_paths`, and the Task 1 schema helpers. Add this method to
  `WorkflowDraftAuthoringApi`:

  ```python
  async def set_step_input_bindings(
      self,
      *,
      workspace_id: str,
      revision: int,
      step_id: str,
      bindings: Sequence[InputBinding],
  ) -> dict[str, Any]:
      """Replace one capability step's canonical input bindings atomically."""
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
          raise ValueError(f"draft step {step_id!r} does not declare a capability use")
      spec = self.context.specs.get_qualified_spec(capability_name)
      capability_schema = (
          spec.input_schema_contract or spec.input_model.model_json_schema()
      )

      targets = [binding.target for binding in bindings]
      if has_overlapping_paths(targets):
          raise _overlapping_input_targets_error(bindings)

      projected_input = _draft_schema(workspace.draft, "input_schema")
      projected_state = _draft_schema(workspace.draft, "state_schema")
      for index, binding in enumerate(bindings):
          target_parts = binding.target.parts
          try:
              schema_fragment_at_path(
                  capability_schema,
                  target_parts,
                  label="capability input schema",
              )
          except ValueError as exc:
              raise ValueError(
                  f"bindings[{index}].target {str(binding.target)!r} "
                  f"is not declared by capability {capability_name!r}: {exc}"
              ) from exc

          if isinstance(binding, InputValueBinding):
              if not target_parts and not isinstance(binding.value, Mapping):
                  raise ValueError(
                      f"bindings[{index}].value for target '.' must be a JSON object"
                  )
              validate_json_value_at_schema_path(
                  schema=capability_schema,
                  parts=target_parts,
                  value=binding.value,
                  label=f"bindings[{index}].value",
              )
              continue

          if isinstance(binding, InputPathBinding):
              source = binding.path
              if source.root == "context":
                  continue
              target_schema = (
                  projected_input if source.root == "input" else projected_state
              )
              if not schema_path_exists(target_schema, source.parts):
                  target_schema = project_schema_path_to_schema_path(
                      target_schema=target_schema,
                      source_schema=capability_schema,
                      source_parts=target_parts,
                      target_parts=source.parts,
                      allow_existing_equivalent=True,
                  )
              if source.root == "input":
                  projected_input = target_schema
              else:
                  projected_state = target_schema

      payload = [binding.model_dump(mode="json") for binding in bindings]
      if (
          step.get("input", []) == payload
          and workspace.draft.get("input_schema", {}) == projected_input
          and workspace.draft.get("state_schema", {}) == projected_state
      ):
          return summarize_draft_workspace(workspace)

      patch = _step_input_bindings_patch(
          workspace=workspace,
          step_id=step_id,
          bindings=payload,
          input_schema=projected_input,
          state_schema=projected_state,
      )
      return await self.drafts.patch_draft_workspace(
          workspace_id=workspace_id,
          revision=revision,
          patch=patch,
      )
  ```

  Implement `_draft_schema`, `_overlapping_input_targets_error`, and
  `_step_input_bindings_patch` as focused private helpers in the same module.
  `_overlapping_input_targets_error` must report both binding indexes by finding
  the first pair for which `paths_overlap(left.target, right.target)` is true.
  `_step_input_bindings_patch` emits schema replacements only when changed and
  always emits one step-input replacement.

  ```python
  def _draft_schema(draft: Mapping[str, Any], key: str) -> dict[str, Any]:
      value = draft.get(key, {})
      if not isinstance(value, dict):
          raise ValueError(f"draft {key} must be an object")
      return deepcopy(value)


  def _overlapping_input_targets_error(
      bindings: Sequence[InputBinding],
  ) -> ValueError:
      for left_index, left in enumerate(bindings):
          for right_index in range(left_index + 1, len(bindings)):
              right = bindings[right_index]
              if paths_overlap(left.target, right.target):
                  return ValueError(
                      f"bindings[{left_index}].target {str(left.target)!r} "
                      f"overlaps bindings[{right_index}].target "
                      f"{str(right.target)!r}"
                  )
      raise AssertionError("overlap error requested without overlapping targets")


  def _step_input_bindings_patch(
      *,
      workspace: WorkflowDraftWorkspace,
      step_id: str,
      bindings: list[dict[str, Any]],
      input_schema: dict[str, Any],
      state_schema: dict[str, Any],
  ) -> list[dict[str, Any]]:
      patch: list[dict[str, Any]] = []
      for key, value in (
          ("input_schema", input_schema),
          ("state_schema", state_schema),
      ):
          if workspace.draft.get(key, {}) != value:
              patch.append({"op": "replace", "path": f"/{key}", "value": value})
      patch.append(
          {
              "op": "replace",
              "path": f"/steps/{escape_json_pointer(step_id)}/input",
              "value": bindings,
          }
      )
      return patch
  ```

- [ ] **Step 6: Add the protocol-neutral delegation**

  Add the exact method signature to `WorkflowApiSurface` and delegate from
  `WorkflowApi`:

  ```python
  async def set_step_input_bindings(
      self,
      *,
      workspace_id: str,
      revision: int,
      step_id: str,
      bindings: Sequence[InputBinding],
  ) -> dict[str, Any]:
      return await self.draft_authoring.set_step_input_bindings(
          workspace_id=workspace_id,
          revision=revision,
          step_id=step_id,
          bindings=bindings,
      )
  ```

- [ ] **Step 7: Run focused API and runtime tests**

  Run:

  ```bash
  uv run pytest tests/wf_api/test_drafts_service.py -k "step_input_bindings or nested" -q
  uv run pytest tests/core/test_nested_mappings.py tests/core/test_canonical_node_bindings.py -q
  uv run ruff check src/wf_api/draft_authoring.py src/wf_api/surface.py src/wf_api/service.py tests/wf_api/test_drafts_service.py
  uv run basedpyright --level error src/wf_api/draft_authoring.py src/wf_api/surface.py src/wf_api/service.py
  ```

  Expected: all pass. Include one API test that compiles and executes the draft,
  asserting the handler receives `request.title`, `request.body`, and
  `request.format` in one object.

- [ ] **Step 8: Commit Task 2**

  ```bash
  git add src/wf_api/draft_authoring.py src/wf_api/surface.py src/wf_api/service.py tests/wf_api/test_drafts_service.py
  git commit -m "feat: replace draft step input bindings"
  ```

---

### Task 3: JSON-RPC Model, Method, And Remote Client

**Files:**
- Modify: `src/wf_transport_rpc_http/models.py`
- Modify: `src/wf_transport_rpc_http/methods/drafts.py`
- Modify: `src/wf_transport_rpc_http/client/drafts.py`
- Test: `tests/wf_transport_rpc_http/test_app.py`
- Test: `tests/wf_transport_rpc_http/test_client.py`

**Interfaces:**
- Consumes: `WorkflowApiSurface.set_step_input_bindings` from Task 2.
- Produces: JSON-RPC method `workflow.draft_workspaces.set_step_input_bindings` and matching `RpcDraftClientMixin` method.

- [ ] **Step 1: Write failing RPC model and application tests**

  Add an application test that sends this request and then inspects the stored
  order:

  ```python
  result = await _rpc(
      client,
      "workflow.draft_workspaces.set_step_input_bindings",
      {
          "workspace_id": "focused_ws",
          "revision": 3,
          "step_id": "call",
          "bindings": [
              {"path": "input.value", "target": "payload.value"},
              {"path": "input.value", "target": "audit.value"},
              {"value": None, "target": "payload.optional"},
          ],
      },
  )
  assert result["result"]["revision"] == 4
  ```

  Add malformed union tests for a binding with both `path` and `value`, and one
  with neither.

- [ ] **Step 2: Write a failing remote-client serialization test**

  ```python
  await client.set_step_input_bindings(
      workspace_id="client_ws",
      revision=2,
      step_id="call",
      bindings=[
          InputPathBinding(path="state.title", target="request.title"),
          InputValueBinding(target="request.format", value="markdown"),
      ],
  )

  assert calls[-1] == (
      "workflow.draft_workspaces.set_step_input_bindings",
      {
          "workspace_id": "client_ws",
          "revision": 2,
          "step_id": "call",
          "bindings": [
              {"target": "request.title", "path": "state.title"},
              {"target": "request.format", "value": "markdown"},
          ],
      },
  )
  ```

- [ ] **Step 3: Run transport tests and confirm RED**

  Run:

  ```bash
  uv run pytest tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py -k "step_input_bindings" -q
  ```

  Expected: failures for the missing params model, method registration, and
  client method.

- [ ] **Step 4: Implement the RPC params, method, and client**

  In `models.py`, reuse the core union:

  ```python
  class SetStepInputBindingsParams(RpcParamsModel):
      workspace_id: str = Field(min_length=1)
      revision: int = Field(ge=1)
      step_id: str = Field(min_length=1)
      bindings: list[InputBinding]
  ```

  Register the method next to the map compatibility method:

  ```python
  @entrypoint.method(
      name="workflow.draft_workspaces.set_step_input_bindings",
      errors=[WorkflowRpcError],
  )
  async def workflow_draft_workspaces_set_step_input_bindings(
      params: SetStepInputBindingsParams = RpcParams(),
  ) -> dict[str, Any]:
      try:
          return await server.api.set_step_input_bindings(
              workspace_id=params.workspace_id,
              revision=params.revision,
              step_id=params.step_id,
              bindings=params.bindings,
          )
      except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
          raise_workflow_rpc_error(exc)
  ```

  Add the client method using `model_dump(mode="json")` for every binding.

- [ ] **Step 5: Run transport verification**

  Run:

  ```bash
  uv run pytest tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py -q
  uv run ruff check src/wf_transport_rpc_http tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py
  uv run basedpyright --level error src/wf_transport_rpc_http
  ```

  Expected: all pass.

- [ ] **Step 6: Commit Task 3**

  ```bash
  git add src/wf_transport_rpc_http tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py
  git commit -m "feat: expose input bindings over rpc"
  ```

---

### Task 4: MCP Canonical Binding Tool

**Files:**
- Modify: `src/wf_mcp/workflow_surface/models.py`
- Modify: `src/wf_mcp/workflow_surface/tools.py`
- Modify: `src/wf_mcp/proxy/runtime.py`
- Test: `tests/wf_mcp/workflow_surface/test_drafts.py`
- Test: `tests/wf_mcp/server/test_config.py`
- Test: `tests/wf_mcp/server/test_tools.py`

**Interfaces:**
- Consumes: Task 2 API method and existing `DraftInputBindings` alias.
- Produces: MCP tool `wf.workflow.set_step_input_bindings`.

- [ ] **Step 1: Write failing MCP request and handler tests**

  Add a request-model test proving path/value union parsing and explicit null.
  Add a workflow-surface test that calls the new tool handler with ordered
  bindings and asserts the stored canonical list. Add server catalog assertions
  for the tool name and that its request schema exposes `bindings` but no
  `merge`.

- [ ] **Step 2: Run MCP tests and confirm RED**

  Run:

  ```bash
  uv run pytest tests/wf_mcp/workflow_surface/test_drafts.py tests/wf_mcp/server/test_config.py tests/wf_mcp/server/test_tools.py -k "step_input_bindings" -q
  ```

  Expected: failures because the request model and tool are absent.

- [ ] **Step 3: Add the request model and tool**

  Reuse the existing alias:

  ```python
  class SetStepInputBindingsRequest(BaseModel):
      """Replace one step's complete canonical input-binding list."""

      workspace_id: WorkspaceId
      revision: int = Field(ge=1, description="Expected current workspace revision.")
      step_id: NonEmptyString
      bindings: DraftInputBindings
  ```

  Register:

  ```python
  @server.tool(
      name="wf.workflow.set_step_input_bindings",
      title="Set Step Input Bindings",
      description=(
          "Replace one capability step's complete canonical input-binding list "
          "atomically. Supports graph-path and literal bindings; inspect the "
          "draft first because replacement is not a merge."
      ),
  )
  async def set_step_input_bindings(
      request: SetStepInputBindingsRequest,
  ) -> DraftWorkspaceResult:
      return DraftWorkspaceResult.model_validate(
          await handlers.set_step_input_bindings(
              workspace_id=request.workspace_id,
              revision=request.revision,
              step_id=request.step_id,
              bindings=request.bindings,
          )
      )
  ```

  Add the tool name to the proxy runtime allowlist next to
  `wf.workflow.set_step_input_map`. Keep the compatibility tool registered.

- [ ] **Step 4: Run MCP verification**

  Run:

  ```bash
  uv run pytest tests/wf_mcp/workflow_surface/test_drafts.py tests/wf_mcp/server/test_config.py tests/wf_mcp/server/test_tools.py -q
  uv run ruff check src/wf_mcp/workflow_surface src/wf_mcp/proxy/runtime.py tests/wf_mcp/workflow_surface/test_drafts.py tests/wf_mcp/server/test_config.py tests/wf_mcp/server/test_tools.py
  uv run basedpyright --level error src/wf_mcp/workflow_surface src/wf_mcp/proxy/runtime.py
  ```

  Expected: all pass and the generated MCP schema contains the canonical union.

- [ ] **Step 5: Commit Task 4**

  ```bash
  git add src/wf_mcp/workflow_surface src/wf_mcp/proxy/runtime.py tests/wf_mcp/workflow_surface/test_drafts.py tests/wf_mcp/server/test_config.py tests/wf_mcp/server/test_tools.py
  git commit -m "feat: expose canonical input bindings to mcp"
  ```

---

### Task 5: Typer Replacement Modes And Remote CLI

**Files:**
- Modify: `src/wf_cli/commands/draft_options.py`
- Modify: `src/wf_cli/commands/draft_add.py`
- Modify: `src/wf_cli/commands/drafts.py`
- Test: `tests/wf_cli/test_app.py`
- Test: `tests/wf_cli/test_remote_target.py`

**Interfaces:**
- Consumes: `WorkflowApiSurface.set_step_input_bindings` and the legacy `set_step_input_map` adapter.
- Produces: canonical `wf draft set-input` replacement modes described by the spec.

- [ ] **Step 1: Write failing parser tests**

  Add tests for a list-preserving path parser that accepts duplicate sources,
  a literal parser that preserves explicit null and JSON strings containing
  `=`, and a bindings-file parser that validates the canonical union:

  ```python
  bindings = parse_step_input_binding_flags(
      ["state.title=request.title", "state.title=audit.title"]
  )
  assert [str(binding.path) for binding in bindings] == [
      "state.title",
      "state.title",
  ]
  ```

  ```python
  values = parse_step_input_value_flags(
      ['request.format="markdown"', "request.optional=null"]
  )
  assert values[0].value == "markdown"
  assert values[1].value is None
  ```

- [ ] **Step 2: Write failing command-mode tests**

  Cover:

  - `--map` plus `--value` calls `set_step_input_bindings` once;
  - `--bindings-file` preserves exact order;
  - `--clear` sends `bindings=[]`;
  - no mode errors;
  - file plus flags errors;
  - `--merge` plus value/file/clear errors;
  - map-only `--merge` still calls `set_step_input_map`;
  - map replacement permits repeated source fan-out.

  Assert compact `typer.BadParameter` text and that handlers are not called on
  invalid combinations.

- [ ] **Step 3: Run CLI tests and confirm RED**

  Run:

  ```bash
  uv run pytest tests/wf_cli/test_app.py -k "set_input" -q
  ```

  Expected: failures for missing options, parsers, and handler delegation.

- [ ] **Step 4: Implement canonical CLI parsers**

  Keep `_parse_step_input_map_flags` unchanged for compatibility. Add list-based
  helpers using canonical models:

  ```python
  _INPUT_BINDINGS_ADAPTER = TypeAdapter(list[InputBinding])


  def validation_error_as_bad_parameter(
      exc: ValidationError,
  ) -> typer.BadParameter:
      """Keep Pydantic failures on Click's concise input-error surface."""
      return typer.BadParameter(str(exc))


  def parse_step_input_binding_flags(
      values: list[str] | None,
  ) -> list[InputPathBinding]:
      bindings: list[InputPathBinding] = []
      for item in values or []:
          source, separator, target = item.partition("=")
          if separator != "=" or not source or not target:
              raise typer.BadParameter("--map must use GRAPH_SOURCE=LOCAL_TARGET")
          try:
              bindings.append(InputPathBinding(path=source, target=target))
          except ValidationError as exc:
              raise validation_error_as_bad_parameter(exc) from exc
      return bindings


  def parse_step_input_value_flags(
      values: list[str] | None,
  ) -> list[InputValueBinding]:
      bindings: list[InputValueBinding] = []
      for item in values or []:
          target, separator, raw_value = item.partition("=")
          if separator != "=" or not target:
              raise typer.BadParameter("--value must use LOCAL_TARGET=JSON")
          try:
              value = json.loads(raw_value)
              bindings.append(InputValueBinding(target=target, value=value))
          except json.JSONDecodeError as exc:
              raise typer.BadParameter(
                  f"--value for {target!r} is invalid JSON: {exc.msg}"
              ) from exc
          except ValidationError as exc:
              raise validation_error_as_bad_parameter(exc) from exc
      return bindings


  def parse_step_input_bindings_file(path: Path) -> list[InputBinding]:
      try:
          return _INPUT_BINDINGS_ADAPTER.validate_python(
              parse_json_file(path, option_name="--bindings-file")
          )
      except ValidationError as exc:
          raise validation_error_as_bad_parameter(exc) from exc
  ```

  Delete private `_as_bad_parameter` from `draft_add.py`, import
  `validation_error_as_bad_parameter` from `draft_options.py`, and replace its
  seven current call sites. This keeps all Pydantic-to-Typer formatting in one
  helper rather than duplicating it.

- [ ] **Step 5: Implement command mode selection**

  Add `--value`, `--bindings-file`, and `--clear` options to `set-input`. Keep
  `--merge` but describe it as compatibility-only. Use explicit mode checks:

  ```python
  has_flags = bool(mapping or literal_values)
  has_file = bindings_file is not None
  selected_modes = sum((has_flags, has_file, clear))
  if selected_modes == 0:
      raise typer.BadParameter(
          "provide --map/--value, --bindings-file, or --clear"
      )
  if selected_modes > 1:
      raise typer.BadParameter(
          "--bindings-file and --clear cannot be combined with --map or --value"
      )
  if merge and (literal_values or has_file or clear):
      raise typer.BadParameter(
          "--merge is supported only for compatibility map-only edits"
      )
  ```

  For `merge=True`, call the unchanged map handler. Otherwise build bindings as
  file order, `[]`, or path flags followed by literal flags, and call
  `set_step_input_bindings`.

- [ ] **Step 6: Add a real remote CLI round trip**

  Extend `tests/wf_cli/test_remote_target.py` to start the local JSON-RPC app,
  create/inspect a draft, export the current input list to a test JSON file,
  replace it with path fan-out plus a literal, and inspect the stored result.
  Assert the recorded method is
  `workflow.draft_workspaces.set_step_input_bindings` and the revision advances
  once.

- [ ] **Step 7: Run CLI verification**

  Run:

  ```bash
  uv run pytest tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py -k "set_input or input_bindings" -q
  uv run ruff check src/wf_cli/commands/draft_options.py src/wf_cli/commands/draft_add.py src/wf_cli/commands/drafts.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py
  uv run basedpyright --level error src/wf_cli/commands/draft_options.py src/wf_cli/commands/draft_add.py src/wf_cli/commands/drafts.py
  ```

  Expected: all pass. Run `uv run wf draft set-input --help` and verify the
  output distinguishes replacement modes from compatibility `--merge`.

- [ ] **Step 8: Commit Task 5**

  ```bash
  git add src/wf_cli/commands/draft_options.py src/wf_cli/commands/draft_add.py src/wf_cli/commands/drafts.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py
  git commit -m "feat: replace draft input bindings from cli"
  ```

---

### Task 6: Documentation, Issue State, Review, And Final Verification

**Files:**
- Modify: `docs/wf_cli.md`
- Modify: `skills/wf-cli/SKILL.md`
- Modify: `skills/wf-workflow/references/draft-workspaces.md`
- Modify: `ISSUES.md`
- Modify: `docs/current_roadmap.md`
- Modify then move: `docs/superpowers/plans/2026-07-22-atomic-step-input-bindings.md`

**Interfaces:**
- Consumes: all completed behavior from Tasks 1-5.
- Produces: current user/agent guidance and an archived completed plan.

- [ ] **Step 1: Update user and agent documentation**

  Document these exact workflows:

  ```bash
  wf draft inspect WS --include-draft |
    jq '.draft.steps.publish.input' > bindings.json

  wf draft set-input WS --revision 4 --step publish \
    --map state.report.title=request.title \
    --map state.report.markdown=request.body \
    --value request.format='"markdown"'

  wf draft set-input WS --revision 5 --step publish \
    --bindings-file bindings.json

  wf draft set-input WS --revision 6 --step publish --clear
  ```

  State plainly that replacement is default, `--bindings-file` is canonical,
  repeated source paths are allowed, and `--merge` is map-only compatibility.

- [ ] **Step 2: Update issue and roadmap state narrowly**

  In `ISSUES.md`, check:

  - atomic structured node input assembly;
  - literal node-input bindings.

  Keep fan-out map loss open and clarify that the canonical replacement avoids
  loss while compatibility map readers/writers can still collapse it. Leave all
  output, step-update, and TypeScript issues open.

  Add one completed roadmap entry linking to the historical plan path.

- [ ] **Step 3: Run the complete focused verification matrix**

  Run:

  ```bash
  uv run pytest \
    tests/wf_api/test_schema_projection.py \
    tests/wf_api/test_drafts_service.py \
    tests/wf_transport_rpc_http/test_app.py \
    tests/wf_transport_rpc_http/test_client.py \
    tests/wf_mcp/workflow_surface/test_drafts.py \
    tests/wf_mcp/server/test_config.py \
    tests/wf_mcp/server/test_tools.py \
    tests/wf_cli/test_app.py \
    tests/wf_cli/test_remote_target.py \
    tests/core/test_nested_mappings.py \
    tests/core/test_canonical_node_bindings.py \
    -q
  uv run ruff check
  uv run ruff format --check
  uv run basedpyright --level error
  ```

  Expected: all tests pass; Ruff and basedpyright report no errors. Existing
  third-party deprecation warnings may remain but must be reported.

- [ ] **Step 4: Run independent review and fix valid findings**

  Use the repository code-review workflow against the design spec and this
  plan. Require reviewers to check:

  - stale-revision precedence;
  - no mutation on semantic failure;
  - exact no-op behavior;
  - fan-out survival through CLI and transport;
  - explicit null preservation;
  - whole-payload projection;
  - absence of duplicate binding models;
  - legacy map merge compatibility.

  Apply valid fixes and rerun the affected focused tests plus Ruff and
  basedpyright.

- [ ] **Step 5: Complete and archive the plan**

  Check every completed task box, then move:

  ```text
  docs/superpowers/plans/2026-07-22-atomic-step-input-bindings.md
  -> docs/historical/superpowers/plans/2026-07-22-atomic-step-input-bindings.md
  ```

  Confirm all live links use the historical path.

- [ ] **Step 6: Commit Task 6**

  ```bash
  git add docs/wf_cli.md skills/wf-cli/SKILL.md \
    skills/wf-workflow/references/draft-workspaces.md ISSUES.md \
    docs/current_roadmap.md docs/superpowers/plans \
    docs/historical/superpowers/plans
  git commit -m "docs: complete atomic step input bindings"
  ```

- [ ] **Step 7: Confirm final repository state**

  Run:

  ```bash
  git status --short
  git log -6 --oneline
  git diff HEAD^ --check
  ```

  Expected: clean worktree, six task commits (plus this plan commit), and no
  whitespace errors.
