# Nested Local Draft Bindings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let focused draft authoring bind nested node-local capability paths while centralizing reusable JSON Schema path lookup and projection.

**Architecture:** Extend `wf_api.schema_projection` with one bounded local-reference resolver, one shared path-existence query, and one nested source-to-target projection operation. `WorkflowDraftAuthoringApi` continues parsing paths with `GraphSourcePath` and `LocalPath`, while existing payload serializers, RPC request shapes, and revision-checked patching remain unchanged. CLI parsing validates implied rootless local targets but does not introduce another path model.

**Tech Stack:** Python 3.14, Pydantic path types, `jsonschema` Draft 2020-12 validation, Typer CLI, FastAPI JSON-RPC transport, pytest, Ruff, basedpyright.

## Global Constraints

- Preserve revision precedence: after intrinsic request validation, a stale revision returns `revision_conflict` before workspace-, path-, or capability-derived semantic errors.
- Use canonical `GraphSourcePath` and `LocalPath`; do not add duplicate Pydantic path models or transport endpoint unions.
- Keep transport request and response shapes unchanged; nested paths remain strings at RPC boundaries.
- Support only bounded local references `#/$defs/...` and `#/definitions/...`; do not build a general JSON Schema resolver or support remote references.
- Preserve existing single-segment syntax and semantics.
- Preserve existing public-output lowering through durable state.
- Do not add literal bindings, fan-out-safe binding lists, structured-input assembly, step metadata, TypeScript RPC parity, or route/revision/runtime changes.
- Add comments or docstrings around local-reference traversal and other non-obvious schema logic.
- Run focused tests before broad regression suites; do not run the repository-wide pytest suite for this slice.

---

### Task 1: Centralize JSON Schema Path Lookup And Projection

**Files:**
- Modify: `src/wf_api/schema_projection.py`
- Modify: `src/wf_api/drafts.py`
- Modify: `src/wf_api/draft_authoring.py`
- Test: `tests/wf_api/test_schema_projection.py`

**Interfaces:**
- Produces: `schema_path_exists(schema: Mapping[str, Any], parts: Sequence[str]) -> bool`
- Produces: `project_schema_path_to_schema_path(*, target_schema: JsonObject, source_schema: JsonObject, source_parts: tuple[str, ...], target_parts: tuple[str, ...], allow_existing_equivalent: bool = False) -> JsonObject`
- Preserves: `project_property_to_schema_path(...)` as a root-property compatibility wrapper.
- Removes: private duplicate `_schema_path_exists` implementations from `wf_api.drafts` and `wf_api.draft_authoring`.

- [x] **Step 1: Add failing tests for inline and referenced nested source paths**

  Extend `tests/wf_api/test_schema_projection.py` imports with the two new public operations, then add these cases:

  ```python
  def test_project_schema_path_copies_inline_nested_source() -> None:
      projected = project_schema_path_to_schema_path(
          target_schema={"type": "object", "properties": {}},
          source_schema={
              "type": "object",
              "properties": {
                  "report": {
                      "type": "object",
                      "properties": {"title": {"type": "string"}},
                  }
              },
          },
          source_parts=("report", "title"),
          target_parts=("document", "title"),
      )

      assert projected["properties"]["document"]["properties"]["title"] == {
          "type": "string"
      }


  def test_project_schema_path_traverses_pydantic_defs_reference() -> None:
      projected = project_schema_path_to_schema_path(
          target_schema={"type": "object", "properties": {}},
          source_schema={
              "type": "object",
              "properties": {"report": {"$ref": "#/$defs/Report"}},
              "$defs": {
                  "Report": {
                      "type": "object",
                      "properties": {
                          "markdown": {"$ref": "#/$defs/Markdown"}
                      },
                  },
                  "Markdown": {"type": "string", "minLength": 1},
              },
          },
          source_parts=("report", "markdown"),
          target_parts=("report", "markdown"),
      )

      assert projected["properties"]["report"]["properties"]["markdown"] == {
          "$ref": "#/$defs/Markdown"
      }
      assert projected["$defs"]["Markdown"]["minLength"] == 1


  def test_project_schema_path_traverses_legacy_definitions_reference() -> None:
      projected = project_schema_path_to_schema_path(
          target_schema={"type": "object", "properties": {}},
          source_schema={
              "type": "object",
              "properties": {"report": {"$ref": "#/definitions/Report"}},
              "definitions": {
                  "Report": {
                      "type": "object",
                      "properties": {"title": {"type": "string"}},
                  }
              },
          },
          source_parts=("report", "title"),
          target_parts=("title",),
      )

      assert projected["properties"]["title"] == {"type": "string"}
      assert "Report" in projected["definitions"]
  ```

- [x] **Step 2: Add failing tests for existence and precise failures**

  Add tests that pin the bounded behavior:

  ```python
  def test_schema_path_exists_follows_local_defs() -> None:
      schema = {
          "type": "object",
          "properties": {"report": {"$ref": "#/$defs/Report"}},
          "$defs": {
              "Report": {
                  "type": "object",
                  "properties": {"title": {"type": "string"}},
              }
          },
      }

      assert schema_path_exists(schema, ("report", "title")) is True
      assert schema_path_exists(schema, ("report", "missing")) is False


  def test_project_schema_path_rejects_missing_nested_source() -> None:
      with pytest.raises(ValueError, match="source schema path 'report.missing' is not declared"):
          project_schema_path_to_schema_path(
              target_schema={"type": "object", "properties": {}},
              source_schema={
                  "type": "object",
                  "properties": {
                      "report": {"type": "object", "properties": {}}
                  },
              },
              source_parts=("report", "missing"),
              target_parts=("value",),
          )


  def test_project_schema_path_rejects_scalar_source_ancestor() -> None:
      with pytest.raises(ValueError, match="source schema path 'report' is not an object"):
          project_schema_path_to_schema_path(
              target_schema={"type": "object", "properties": {}},
              source_schema={
                  "type": "object",
                  "properties": {"report": {"type": "string"}},
              },
              source_parts=("report", "title"),
              target_parts=("title",),
          )


  def test_project_schema_path_rejects_remote_reference() -> None:
      with pytest.raises(ValueError, match="unsupported reference 'https://example.com/report.json'"):
          project_schema_path_to_schema_path(
              target_schema={"type": "object", "properties": {}},
              source_schema={
                  "type": "object",
                  "properties": {
                      "report": {"$ref": "https://example.com/report.json"}
                  },
              },
              source_parts=("report", "title"),
              target_parts=("title",),
          )
  ```

  Retain the existing target-conflict and equivalent-target tests; they are regression coverage for the generalized operation.

- [x] **Step 3: Run the schema tests and confirm the new imports fail**

  Run:

  ```bash
  uv run pytest tests/wf_api/test_schema_projection.py -q -n 0
  ```

  Expected: collection fails because `schema_path_exists` and `project_schema_path_to_schema_path` are not exported yet.

- [x] **Step 4: Implement one bounded path resolver and the generalized projector**

  In `src/wf_api/schema_projection.py`:

  - import `Mapping` and `Sequence` from `collections.abc`;
  - add a private `_resolve_local_reference(root_schema, candidate, label)` helper that accepts only `#/$defs/<name>` and `#/definitions/<name>`, checks the selected definition is a mapping, and raises a precise `ValueError` for unsupported or unresolved references;
  - add a private `_schema_at_path(root_schema, parts, *, label)` helper that resolves local references before reading each intermediate object's `properties`;
  - make `schema_path_exists` call `_schema_at_path` and return `False` for missing paths, non-object ancestors, or unresolved references;
  - move the current target-path insertion and definition-block merge into `project_schema_path_to_schema_path` after selecting the nested source schema;
  - make `project_property_to_schema_path` delegate with `source_parts=(source_field,)` and translate root-field errors where needed to preserve existing wording.

  The implementation must retain the selected leaf unchanged. For example, when the leaf is `{"$ref": "#/$defs/Markdown"}`, copy that reference and merge the source definition blocks rather than replacing the leaf with the resolved definition.

- [x] **Step 5: Replace both duplicate existence helpers with the shared function**

  In `src/wf_api/drafts.py` and `src/wf_api/draft_authoring.py`:

  ```python
  from .schema_projection import schema_path_exists
  ```

  Delete each private `_schema_path_exists` definition and replace its callers with `schema_path_exists(...)`. Remove now-unused `Mapping` or `Sequence` imports only when no other symbol in that module needs them.

- [x] **Step 6: Run focused tests and quality checks**

  Run:

  ```bash
  uv run pytest tests/wf_api/test_schema_projection.py tests/wf_api/test_drafts_service.py -q -n 0
  uv run ruff check src/wf_api/schema_projection.py src/wf_api/drafts.py src/wf_api/draft_authoring.py tests/wf_api/test_schema_projection.py
  uv run ruff format --check src/wf_api/schema_projection.py src/wf_api/drafts.py src/wf_api/draft_authoring.py tests/wf_api/test_schema_projection.py
  uv run basedpyright --level error src/wf_api/schema_projection.py src/wf_api/drafts.py src/wf_api/draft_authoring.py
  ```

  Expected: all schema projection and draft service tests pass; all quality checks are clean.

- [x] **Step 7: Commit the shared schema operation**

  ```bash
  git add src/wf_api/schema_projection.py src/wf_api/drafts.py src/wf_api/draft_authoring.py tests/wf_api/test_schema_projection.py
  git commit -m "refactor: centralize schema path projection"
  ```

---

### Task 2: Support Nested Local Paths In Focused Draft Bind

**Files:**
- Modify: `src/wf_api/draft_authoring.py`
- Test: `tests/wf_api/test_drafts_service.py`

**Interfaces:**
- Consumes: `project_schema_path_to_schema_path(...)` and `schema_path_exists(...)` from Task 1.
- Preserves: `WorkflowDraftAuthoringApi.bind_draft(...)` request and response signatures.
- Produces: complete nested `LocalPath` values in existing input/output binding payloads.

- [x] **Step 1: Add a nested capability fixture with Pydantic-style definitions**

  Add this test-only capability beside the existing echo/snapshot fixtures in `tests/wf_api/test_drafts_service.py`:

  ```python
  class _ReportInputValue(BaseModel):
      title: str


  class _NestedReportInput(BaseModel):
      report: _ReportInputValue


  class _ReportOutputValue(BaseModel):
      markdown: str


  class _NestedReportOutput(BaseModel):
      report: _ReportOutputValue


  @node(name="nested_report", outcomes=("ok",))
  def _nested_report(payload: _NestedReportInput) -> _NestedReportOutput:
      return _NestedReportOutput(
          report=_ReportOutputValue(markdown=f"# {payload.report.title}")
      )
  ```

  Register it in each new test with the same existing connection setup used for `_snapshot_tool`:

  ```python
  service.register_specs("demo.personal", _nested_report)
  ```

- [x] **Step 2: Add failing input/state-to-local tests**

  Add tests that call:

  ```python
  await authoring.bind_draft(
      workspace_id="nested",
      revision=1,
      step_id="render",
      source_path="input.title",
      target_path="local.report.title",
  )
  ```

  and, in a separate workspace:

  ```python
  await authoring.bind_draft(
      workspace_id="nested_state",
      revision=1,
      step_id="render",
      source_path="state.report.title",
      target_path="local.report.title",
  )
  ```

  Assert field-level results:

  ```python
  assert draft["input_schema"]["properties"]["title"]["type"] == "string"
  assert draft["steps"]["render"]["input"] == [
      {"target": "report.title", "path": "input.title"}
  ]
  ```

  For the state case, assert the nested state schema remains valid and the stored target is exactly `report.title`.

- [x] **Step 3: Add failing nested local-output tests**

  Cover both supported directions:

  ```python
  local.report.markdown -> state.report.markdown
  local.report.markdown -> output.report.markdown
  ```

  For state, assert:

  ```python
  assert draft["steps"]["render"]["output"] == [
      {"source": "report.markdown", "target": "state.report.markdown"}
  ]
  assert draft["state_schema"]["properties"]["report"]["properties"]["markdown"]["type"] == "string"
  ```

  For public output, assert the existing lowering contract:

  ```python
  assert draft["steps"]["render"]["output"] == [
      {"source": "report.markdown", "target": "state.report.markdown"}
  ]
  assert draft["output"] == [
      {"path": "state.report.markdown", "target": "report.markdown"}
  ]
  ```

  Also assert both `state_schema` and `output_schema` contain the projected nested string schema.

- [x] **Step 4: Add failure atomicity and revision-precedence tests**

  Add one current-revision test using `local.report.missing -> state.report.missing`. Assert the complete path appears in the `ValueError`, then fetch the workspace and assert `revision == 1` and the step output remains unchanged.

  Add one stale-revision test with the same invalid nested path after first moving the workspace to revision 2. Assert the returned diagnostic code is `revision_conflict` and no nested-path `ValueError` escapes.

- [x] **Step 5: Run the new API tests and confirm the one-field restriction fails**

  Run:

  ```bash
  uv run pytest tests/wf_api/test_drafts_service.py -q -n 0 -k "nested and bind"
  ```

  Expected: nested local endpoints fail with `local path must name one capability field`.

- [x] **Step 6: Replace root-field handling with complete local parts**

  In `WorkflowDraftAuthoringApi.bind_draft`:

  - delete `_local_field`;
  - use the already-parsed `source_parts` or `target_parts` tuple for local endpoints;
  - call `project_schema_path_to_schema_path` with the complete local path as `source_parts`;
  - serialize complete local paths with `format_toml_path_segments(local_parts)` when updating the focused input/output maps;
  - retain `schema_path_exists` reuse for already-declared workflow input/state paths;
  - retain `allow_existing_equivalent=True` for state/output projections;
  - retain existing public-output replacement and state-lowering behavior.

  The relevant input branch becomes structurally equivalent to:

  ```python
  local_path = format_toml_path_segments(target_parts)
  projected = (
      target_schema
      if schema_path_exists(target_schema, source_parts)
      else project_schema_path_to_schema_path(
          target_schema=target_schema,
          source_schema=input_schema,
          source_parts=target_parts,
          target_parts=source_parts,
      )
  )
  input_map = {
      **_input_map_from_payload(step.get("input", [])),
      source_path: local_path,
  }
  ```

- [x] **Step 7: Run focused API and canonical-model regressions**

  Run:

  ```bash
  uv run pytest tests/wf_api/test_drafts_service.py tests/core/test_nested_mappings.py tests/core/test_mapping_validation.py -q -n 0
  uv run ruff check src/wf_api/draft_authoring.py tests/wf_api/test_drafts_service.py
  uv run ruff format --check src/wf_api/draft_authoring.py tests/wf_api/test_drafts_service.py
  uv run basedpyright --level error src/wf_api/draft_authoring.py
  ```

  Expected: nested and existing single-field cases pass, and canonical nested mapping validation remains green.

- [x] **Step 8: Commit focused nested bind support**

  ```bash
  git add src/wf_api/draft_authoring.py tests/wf_api/test_drafts_service.py
  git commit -m "feat: bind nested local draft paths"
  ```

---

### Task 3: Support Nested Capability Maps Through CLI And RPC

**Files:**
- Modify: `src/wf_api/draft_authoring.py`
- Modify: `src/wf_cli/commands/draft_options.py`
- Modify: `src/wf_cli/commands/drafts.py`
- Modify: `src/wf_cli/commands/draft_add.py`
- Modify: `src/wf_mcp/workflow_surface/models.py`
- Test: `tests/wf_api/test_drafts_service.py`
- Test: `tests/wf_transport_rpc_http/test_app.py`
- Test: `tests/wf_transport_rpc_http/test_client.py`
- Test: `tests/wf_cli/test_app.py`
- Test: `tests/wf_cli/test_remote_target.py`

**Interfaces:**
- Consumes: complete nested schema selection from Task 1.
- Preserves: `add_step_from_capability(..., input_map: dict[str, str] | None, ...)` and all transport envelopes.
- Produces: validated rootless local map targets such as `report.title` in CLI commands.

- [x] **Step 1: Add failing capability-add API coverage**

  In `tests/wf_api/test_drafts_service.py`, add a test that creates an empty-schema draft and calls:

  ```python
  result = await authoring.add_step_from_capability(
      workspace_id="nested_add",
      revision=1,
      step_id="render",
      capability_name="demo.personal.nested_report",
      routes={"ok": "__end__"},
      input_map={"input.title": "report.title"},
      bind_outputs={},
  )
  ```

  Assert revision 2, stored target `report.title`, and projected workflow input schema `title: string`. Validate or compile the resulting draft through the existing draft validation API and assert `status == "valid"`.

- [x] **Step 2: Add failing CLI parser and help tests**

  In `tests/wf_cli/test_app.py`, add assertions that:

  - `wf draft set-input ... --map input.title=report.title` reaches the handler with the nested string unchanged;
  - `wf draft add capability ... --input input.title=report.title` reaches the handler unchanged;
  - `--map input.title=local.report.title` exits with code 2 and suggests `input.title=report.title`;
  - malformed rootless local paths fail before RPC;
  - `wf draft bind --help` describes explicit rooted endpoints such as `local.report.title`;
  - set-input and capability-add help describe rootless local paths such as `report.title`.

- [x] **Step 3: Add failing transport preservation tests**

  In `tests/wf_transport_rpc_http/test_app.py` and `tests/wf_transport_rpc_http/test_client.py`, extend the existing bind and add-capability tests with nested values. Assert request delegation and stored results preserve:

  ```python
  source_path == "input.title"
  target_path == "local.report.title"
  input_map == {"input.title": "report.title"}
  ```

  In `tests/wf_cli/test_remote_target.py`, assert the remote CLI emits the existing JSON-RPC method names and unchanged nested strings. Do not add new RPC models or methods.

- [x] **Step 4: Run focused tests and confirm nested projection/help failures**

  Run:

  ```bash
  uv run pytest tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py -q -n 0 -k "nested or bind_help or add_step_from_capability"
  ```

  Expected: the add-capability test fails because nested local input paths are skipped; CLI validation/help assertions fail until implemented.

- [x] **Step 5: Project nested capability input paths instead of skipping them**

  In `WorkflowDraftAuthoringApi.add_step_from_capability`:

  - keep parsing graph sources with `_graph_parts` and targets with `LocalPath.parse`;
  - remove `len(local_parts) != 1` from the skip condition;
  - call `project_schema_path_to_schema_path` with `source_parts=local_parts`;
  - continue reusing existing workflow source paths with `schema_path_exists`;
  - preserve the current revision preflight and atomic patch.

  Invalid canonical paths may retain current request-layer behavior, but a valid nested local path must never silently skip schema projection.

- [x] **Step 6: Validate rootless local targets and clarify help**

  In `_parse_step_input_map_flags`, retain the rooted-target repair first, then validate each rootless target:

  ```python
  try:
      LocalPath.parse(target)
  except PathResolutionError as exc:
      raise typer.BadParameter(
          f"{option_name} target {target!r} must be a rootless node-local "
          "path such as report.title or ."
      ) from exc
  ```

  Update command docstrings/help in `drafts.py` and `draft_add.py` to distinguish:

  ```text
  bind endpoint: --from input.title --to local.report.title
  implied local map: --map input.title=report.title
  ```

  Update only descriptions in `BindDraftRequest` and the capability-add request model in `src/wf_mcp/workflow_surface/models.py`; do not alter fields or add validation models.

- [x] **Step 7: Run API, RPC, client, and CLI tests**

  Run:

  ```bash
  uv run pytest tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py -q -n 0
  uv run ruff check src/wf_api/draft_authoring.py src/wf_cli/commands/draft_options.py src/wf_cli/commands/drafts.py src/wf_cli/commands/draft_add.py src/wf_mcp/workflow_surface/models.py tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py
  uv run ruff format --check src/wf_api/draft_authoring.py src/wf_cli/commands/draft_options.py src/wf_cli/commands/drafts.py src/wf_cli/commands/draft_add.py src/wf_mcp/workflow_surface/models.py tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py
  uv run basedpyright --level error src/wf_api/draft_authoring.py src/wf_cli src/wf_mcp/workflow_surface/models.py
  ```

  Expected: all focused layers pass with no request-schema changes.

- [x] **Step 8: Commit nested capability-map and surface support**

  ```bash
  git add src/wf_api/draft_authoring.py src/wf_cli/commands/draft_options.py src/wf_cli/commands/drafts.py src/wf_cli/commands/draft_add.py src/wf_mcp/workflow_surface/models.py tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py
  git commit -m "feat: accept nested local capability maps"
  ```

---

### Task 4: Update User Guidance, Close Covered Issues, And Verify The Slice

**Files:**
- Modify: `skills/wf-cli/SKILL.md`
- Modify: `skills/wf-workflow/references/draft-workspaces.md`
- Modify: `docs/wf_cli.md`
- Modify: `ISSUES.md`
- Modify: `docs/current_roadmap.md`
- Move after verification: `docs/superpowers/plans/2026-07-22-nested-local-draft-bindings.md` to `docs/historical/superpowers/plans/2026-07-22-nested-local-draft-bindings.md`

**Interfaces:**
- Documents: explicit rooted bind endpoints versus implied rootless map targets.
- Closes only: nested bind rejection, capability-add nested projection skip, and stale CLI/agent guidance.
- Leaves open: structured-input assembly, literals, fan-out maps, nested workflow-output source projection, metadata/update-step, and TypeScript parity.

- [ ] **Step 1: Update CLI and agent-facing examples**

  Replace “bare field” wording with “rootless node-local path” in all three live user-facing documents. Include both forms together:

  ```bash
  wf draft bind report_ws --revision 2 --step render \
    --from input.title --to local.report.title

  wf draft set-input report_ws --revision 3 --step render \
    --map input.title=report.title
  ```

  Explain that `wf draft bind` names both rooted endpoints, while `set-input` and capability-add already imply the local side and therefore accept rootless targets. Do not claim support for literals, fan-out, or atomic object assembly.

- [ ] **Step 2: Update issue and roadmap state precisely**

  In `ISSUES.md`, check only these three entries:

  - nested `wf draft bind` local paths;
  - nested capability-step schema projection;
  - CLI help and agent instruction coverage.

  Keep every other `Draft data-shaping parity` entry unchecked.

  In `docs/current_roadmap.md`, add a completed entry summarizing nested local bind/capability map parity and link to:

  ```text
  historical/superpowers/plans/2026-07-22-nested-local-draft-bindings.md
  ```

- [ ] **Step 3: Run the complete focused verification matrix**

  Run:

  ```bash
  uv run pytest tests/wf_api/test_schema_projection.py tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py tests/core/test_nested_mappings.py tests/core/test_mapping_validation.py -q -n 0
  uv run ruff check src/wf_api/schema_projection.py src/wf_api/drafts.py src/wf_api/draft_authoring.py src/wf_cli/commands/draft_options.py src/wf_cli/commands/drafts.py src/wf_cli/commands/draft_add.py src/wf_mcp/workflow_surface/models.py tests/wf_api/test_schema_projection.py tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py
  uv run ruff format --check src/wf_api/schema_projection.py src/wf_api/drafts.py src/wf_api/draft_authoring.py src/wf_cli/commands/draft_options.py src/wf_cli/commands/drafts.py src/wf_cli/commands/draft_add.py src/wf_mcp/workflow_surface/models.py tests/wf_api/test_schema_projection.py tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py
  uv run basedpyright --level error src/wf_api/schema_projection.py src/wf_api/drafts.py src/wf_api/draft_authoring.py src/wf_cli src/wf_mcp/workflow_surface/models.py
  git diff --check
  ```

  Expected: all focused tests and static checks pass. The pytest count may increase as tests are added; report exact totals rather than copying a planned count.

- [ ] **Step 4: Run an independent two-axis review**

  Use the `requesting-code-review` skill against the implementation start commit. Review:

  1. Standards: repository conventions, duplicate schema logic, compatibility-only branches, test quality, comments around reference resolution.
  2. Spec: every requirement in `docs/superpowers/specs/2026-07-22-nested-local-draft-bindings-design.md`, especially stale-revision precedence and unchanged transport shapes.

  Fix Critical and Important findings, rerun affected focused tests, and record any intentional Minor deferrals in the final report.

- [ ] **Step 5: Archive the completed plan and commit documentation**

  After all checks pass:

  ```bash
  git mv docs/superpowers/plans/2026-07-22-nested-local-draft-bindings.md docs/historical/superpowers/plans/2026-07-22-nested-local-draft-bindings.md
  git add ISSUES.md docs/current_roadmap.md docs/wf_cli.md skills/wf-cli/SKILL.md skills/wf-workflow/references/draft-workspaces.md docs/historical/superpowers/plans/2026-07-22-nested-local-draft-bindings.md
  git commit -m "docs: complete nested local draft bindings"
  ```

  Confirm `git status --short` is clean and report changed behavior, exact verification results, deviations, bugs fixed, and review findings.

---

## Self-Review

- **Spec coverage:** Task 1 covers shared schema lookup, bounded local refs, definition propagation, validation, conflicts, and duplicate-helper removal. Task 2 covers focused bind in every scoped direction, lowering, atomic failure, and revision precedence. Task 3 covers capability insertion, CLI validation/help, and unchanged RPC delegation. Task 4 covers live docs, issue state, roadmap, archive, and the full verification gate.
- **Placeholder scan:** Every code change names the concrete behavior, signature, error, or assertion required. No deferred fill-in steps or generic error-handling instructions remain.
- **Type consistency:** Every later task consumes the exact public signatures defined in Task 1. `bind_draft`, `add_step_from_capability`, transport request fields, and focused payload serializer signatures remain unchanged.
