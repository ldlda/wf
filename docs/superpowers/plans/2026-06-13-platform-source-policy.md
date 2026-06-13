# Platform Source Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mark built-in `wf.*` capability sources as platform sources so artifacts/deployments do not need self-bindings such as `wf.std=wf.std`.

**Architecture:** Add a small `SourcePolicy` value on `CapabilitySource` that distinguishes account-bound external sources from process-provided platform sources. Artifact requirement inference and deployment validation should skip binding requirements for platform sources, while runtime dependency resolution still resolves platform node names by exact source id. External source providers keep the current logical-source binding behavior.

**Tech Stack:** Python 3.14 dataclasses/Pydantic snapshots, `wf_platform.CapabilitySource`, `wf_artifacts` validation/factory, `wf_api.runtime_dependencies`, pytest.

---

## File Structure

- Modify `src/wf_platform/sources.py`: add `SourcePolicy`, snapshot model, and `CapabilitySource.policy`.
- Modify `src/wf_api/local_sources.py`: mark built-in `wf.*` sources as platform sources.
- Modify MCP broker-local source creation if needed: `src/wf_mcp/broker/service/core.py` or source factory files that create `wf.recipes`/`wf.mcp`.
- Modify `src/wf_artifacts/models.py`: add `platform: bool = False` to `AvailableSource`.
- Modify `src/wf_api/deployments.py`: project source policy into `AvailableSource`.
- Modify `src/wf_artifacts/validation.py`: skip binding lookup for platform required capabilities.
- Modify `src/wf_api/artifacts.py`: stop suggesting/returning required logical sources for platform sources.
- Modify tests:
  - `tests/platform/test_sources.py`
  - `tests/wf_server/test_local_static_server.py`
  - `tests/wf_transport_rpc_http/test_app.py`
  - `tests/wf_api/test_artifact_api.py`
  - `tests/artifacts/test_validation.py`

---

### Task 1: Add Source Policy Metadata

**Files:**
- Modify: `src/wf_platform/sources.py`
- Test: `tests/platform/test_sources.py`

- [ ] **Step 1: Add failing source policy test**

In `tests/platform/test_sources.py`, add:

```python
def test_capability_source_exposes_policy_snapshot() -> None:
    source = CapabilitySource(
        id="wf.std",
        kind="system",
        policy=SourcePolicy(platform=True, binding_required=False),
    )

    status = source.as_status()

    assert status.policy.platform is True
    assert status.policy.binding_required is False
    assert status.model_dump(mode="json")["policy"] == {
        "platform": True,
        "binding_required": False,
    }
```

Update imports in that test file:

```python
from wf_platform import CapabilitySource, SourcePolicy
```

- [ ] **Step 2: Run test and confirm failure**

Run:

```bash
uv run pytest tests/platform/test_sources.py::test_capability_source_exposes_policy_snapshot -q
```

Expected: fails because `SourcePolicy` does not exist.

- [ ] **Step 3: Implement source policy**

In `src/wf_platform/sources.py`, add after `SourcePermissions`:

```python
@dataclass(frozen=True, slots=True)
class SourcePolicy:
    """Runtime/deployment policy for one capability source.

    Platform sources are process-provided built-ins such as `wf.std`. They are
    not account-bound and should not require deployment source bindings.
    """

    platform: bool = False
    binding_required: bool = True
```

Add snapshot model after `SourcePermissionsSnapshot`:

```python
class SourcePolicySnapshot(BaseModel):
    """Serializable source policy used by CLI/API inventory responses."""

    platform: bool = False
    binding_required: bool = True
```

Add to `SourceStatus`:

```python
policy: SourcePolicySnapshot
```

Add to `CapabilitySource`:

```python
policy: SourcePolicy = field(default_factory=SourcePolicy)
```

Add to `as_status()`:

```python
policy=SourcePolicySnapshot(
    platform=self.policy.platform,
    binding_required=self.policy.binding_required,
),
```

In `src/wf_platform/__init__.py`, export `SourcePolicy` if the package uses lazy exports. Add it beside `SourcePermissions`.

- [ ] **Step 4: Run test and commit**

Run:

```bash
uv run pytest tests/platform/test_sources.py::test_capability_source_exposes_policy_snapshot -q
uv run basedpyright --level error src/wf_platform/sources.py src/wf_platform/__init__.py tests/platform/test_sources.py
```

Expected: test passes and typecheck has 0 errors.

Commit:

```bash
git add src/wf_platform/sources.py src/wf_platform/__init__.py tests/platform/test_sources.py
git commit -m "feat: add capability source policy metadata"
```

---

### Task 2: Mark Built-In Platform Sources

**Files:**
- Modify: `src/wf_api/local_sources.py`
- Modify: `src/wf_mcp/broker/service/core.py` or the exact file that creates `wf.recipes` / `wf.mcp` sources
- Test: `tests/wf_server/test_local_static_server.py`
- Test: `tests/wf_mcp/service/test_catalog.py`

- [ ] **Step 1: Add tests for platform source policy**

In `tests/wf_server/test_local_static_server.py`, add:

```python
def test_local_static_builtins_are_platform_sources(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path)

    wf_std = server.context.specs.capability_sources["wf.std"]

    assert wf_std.policy.platform is True
    assert wf_std.policy.binding_required is False
```

In `tests/wf_mcp/service/test_catalog.py`, add or extend an existing broker-local source test:

```python
def test_broker_local_sources_are_platform_sources() -> None:
    service = WfMcpService()

    wf_recipes = service.capability_sources["wf.recipes"]

    assert wf_recipes.policy.platform is True
    assert wf_recipes.policy.binding_required is False
```

If `WfMcpService()` needs stores/adapters in the existing tests, use that file's existing service fixture/helper.

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
uv run pytest tests/wf_server/test_local_static_server.py::test_local_static_builtins_are_platform_sources tests/wf_mcp/service/test_catalog.py::test_broker_local_sources_are_platform_sources -q
```

Expected: fails because sources still have default external policy.

- [ ] **Step 3: Mark built-ins**

In `src/wf_api/local_sources.py`, import `SourcePolicy`:

```python
from wf_platform import SourcePolicy
```

For every built-in `CapabilitySource(id="wf.std", ...)` and related local static `wf.*` source, set:

```python
policy=SourcePolicy(platform=True, binding_required=False),
```

In the MCP broker file that creates `wf.recipes`, `wf.mcp`, or other broker-local `wf.*` sources, set the same policy:

```python
policy=SourcePolicy(platform=True, binding_required=False),
```

Do not mark upstream MCP connection sources or Python configured sources as platform.

- [ ] **Step 4: Run tests and commit**

Run:

```bash
uv run pytest tests/wf_server/test_local_static_server.py::test_local_static_builtins_are_platform_sources tests/wf_mcp/service/test_catalog.py::test_broker_local_sources_are_platform_sources -q
uv run ruff check src/wf_api/local_sources.py src/wf_mcp/broker tests/wf_server/test_local_static_server.py tests/wf_mcp/service/test_catalog.py
```

Expected: tests pass and ruff is clean.

Commit:

```bash
git add src/wf_api/local_sources.py src/wf_mcp tests/wf_server/test_local_static_server.py tests/wf_mcp/service/test_catalog.py
git commit -m "feat: mark wf builtins as platform sources"
```

---

### Task 3: Make Deployment Validation Binding-Free For Platform Sources

**Files:**
- Modify: `src/wf_artifacts/models.py`
- Modify: `src/wf_api/deployments.py`
- Modify: `src/wf_artifacts/validation.py`
- Test: `tests/artifacts/test_validation.py`

- [ ] **Step 1: Add validation tests**

In `tests/artifacts/test_validation.py`, add:

```python
from wf_artifacts import AvailableSource


def test_platform_source_requirement_does_not_need_binding() -> None:
    artifact = artifact_with(required_capability(logical_source="wf.std", name="replace"))
    deployment = WorkflowDeployment(
        id="demo.default",
        artifact_id=artifact.id,
        artifact_version=artifact.version,
        bindings={},
    )

    diagnostics = validate_deployment_dependencies(
        artifact=artifact,
        deployment=deployment,
        sources=[
            AvailableSource(
                id="wf.std",
                platform=True,
                capabilities={
                    "replace": AvailableCapability(name="replace", kind="node_spec")
                },
            )
        ],
    )

    assert diagnostics == []


def test_missing_platform_source_still_reports_source_missing() -> None:
    artifact = artifact_with(required_capability(logical_source="wf.std", name="replace"))
    deployment = WorkflowDeployment(
        id="demo.default",
        artifact_id=artifact.id,
        artifact_version=artifact.version,
        bindings={},
    )

    diagnostics = validate_deployment_dependencies(
        artifact=artifact,
        deployment=deployment,
        sources=[],
    )

    assert [diagnostic.code for diagnostic in diagnostics] == ["source_missing"]
    assert diagnostics[0].bound_source == "wf.std"
```

If `required_capability()` helper uses different argument names, adapt the calls to the helper already in the file. The required capability must represent `wf.std.replace`.

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
uv run pytest tests/artifacts/test_validation.py::test_platform_source_requirement_does_not_need_binding tests/artifacts/test_validation.py::test_missing_platform_source_still_reports_source_missing -q
```

Expected: first test fails with `binding_missing`; `AvailableSource(platform=True)` may also fail before model update.

- [ ] **Step 3: Add platform flag to available source projection**

In `src/wf_artifacts/models.py`, add to `AvailableSource`:

```python
platform: bool = False
```

In `src/wf_api/deployments.py`, change `AvailableSource(...)` construction to include:

```python
platform=source.policy.platform,
```

- [ ] **Step 4: Update validation logic**

In `src/wf_artifacts/validation.py`, build `sources_by_id` before binding checks, then replace:

```python
bound_source_id = bindings.get(required.logical_source)
if bound_source_id is None:
    diagnostics.append(...)
    continue
```

with:

```python
platform_source = sources_by_id.get(required.logical_source)
if platform_source is not None and platform_source.platform:
    bound_source_id = required.logical_source
else:
    bound_source_id = bindings.get(required.logical_source)
    if bound_source_id is None:
        diagnostics.append(
            _diagnostic(
                code="binding_missing",
                logical_ref=logical_ref,
                required=required,
                message=(
                    f"No binding exists for logical source "
                    f"{required.logical_source!r}."
                ),
                repair_hint=(
                    "Bind the logical source to a compatible concrete source."
                ),
            )
        )
        continue
```

Then keep the existing source lookup:

```python
source = sources_by_id.get(bound_source_id)
```

If no source exists and no binding exists, platform source absence should produce `source_missing` with `bound_source="wf.std"` as covered by the test.

- [ ] **Step 5: Run tests and commit**

Run:

```bash
uv run pytest tests/artifacts/test_validation.py -q
uv run basedpyright --level error src/wf_artifacts/models.py src/wf_artifacts/validation.py src/wf_api/deployments.py tests/artifacts/test_validation.py
```

Expected: validation tests pass and typecheck has 0 errors.

Commit:

```bash
git add src/wf_artifacts/models.py src/wf_artifacts/validation.py src/wf_api/deployments.py tests/artifacts/test_validation.py
git commit -m "feat: skip bindings for platform sources"
```

---

### Task 4: Remove Platform Sources From Required Binding UX

**Files:**
- Modify: `src/wf_api/artifacts.py`
- Test: `tests/wf_api/test_artifact_api.py`
- Test: `tests/wf_transport_rpc_http/test_app.py`

- [ ] **Step 1: Add API tests**

In `tests/wf_api/test_artifact_api.py`, add:

```python
async def test_create_artifact_from_workspace_excludes_platform_sources_from_required_bindings(tmp_path: Path) -> None:
    api = _api(tmp_path)
    workspace = await api.create_draft_workspace_from_capability(
        workspace_id="constant_ws",
        capability_name="wf.std.constant",
        name="constant_value",
    )

    saved = await api.create_artifact_from_workspace(
        workspace_id=workspace["workspace_id"],
        artifact_id="constant_artifact",
        version=1,
        title="Constant Artifact",
        outcomes=["ok"],
    )

    assert saved["saved"] is True
    assert saved["required_logical_sources"] == []
    assert saved["suggested_bindings"] == {}
```

Use the existing helper names in the file if `_api()` or method names differ.

- [ ] **Step 2: Run test and confirm failure**

Run:

```bash
uv run pytest tests/wf_api/test_artifact_api.py::test_create_artifact_from_workspace_excludes_platform_sources_from_required_bindings -q
```

Expected: fails because `wf.std` is currently returned as required/suggested.

- [ ] **Step 3: Filter platform sources in artifact save response**

In `src/wf_api/artifacts.py`, add a helper near `_suggested_self_bindings`:

```python
def _binding_required_sources(
    required_capabilities: dict[str, RequiredCapability],
    sources: dict[str, CapabilitySource],
) -> list[str]:
    return sorted(
        {
            capability.logical_source
            for capability in required_capabilities.values()
            if sources.get(capability.logical_source) is None
            or sources[capability.logical_source].policy.binding_required
        }
    )
```

Import `CapabilitySource` if needed:

```python
from wf_platform import CapabilitySource
```

Replace the `required_sources = sorted({...})` block in `create_artifact_from_draft()` with:

```python
required_sources = _binding_required_sources(
    workflow_artifact.required_capability_map(),
    self.context.specs.capability_sources,
)
```

Change `_suggested_self_bindings()` to return `{}` or remove `wf.std`/`wf.mcp` special casing:

```python
def _suggested_self_bindings(required_sources: Sequence[str]) -> dict[str, str]:
    """Suggest local bindings for external sources that deploy to themselves."""
    return {}
```

This keeps response shape stable while avoiding platform-source binding suggestions.

- [ ] **Step 4: Run tests and commit**

Run:

```bash
uv run pytest tests/wf_api/test_artifact_api.py tests/wf_transport_rpc_http/test_app.py -q
uv run ruff check src/wf_api/artifacts.py tests/wf_api/test_artifact_api.py tests/wf_transport_rpc_http/test_app.py
uv run basedpyright --level error src/wf_api/artifacts.py tests/wf_api/test_artifact_api.py tests/wf_transport_rpc_http/test_app.py
```

Expected: tests pass, ruff clean, typecheck 0 errors.

Commit:

```bash
git add src/wf_api/artifacts.py tests/wf_api/test_artifact_api.py tests/wf_transport_rpc_http/test_app.py
git commit -m "fix: hide platform sources from binding prompts"
```

---

### Task 5: Runtime E2E Without `wf.std` Binding

**Files:**
- Test: `tests/wf_server/test_local_static_server.py`
- Test: `tests/wf_transport_rpc_http/test_app.py`
- Docs: `docs/current_roadmap.md`

- [ ] **Step 1: Add no-binding run tests**

In `tests/wf_server/test_local_static_server.py`, add a variant of the existing
`test_local_static_server_runs_deployment_and_persists_run` that uses the
existing `_constant_plan()` helper, but removes every `wf.std=wf.std` binding:

```python
async def test_local_static_wf_std_deployment_runs_without_source_binding(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    api = server.api
    plan = _constant_plan()

    artifact_result = await api.create_artifact_from_plan(
        artifact_id="server_constant_no_binding",
        version=1,
        title="Server Constant No Binding",
        plan=plan.model_copy(update={"name": "server_constant_no_binding"}),
        outcomes=["ok"],
        source_bindings={},
    )
    deployment_result = await api.save_deployment(
        {
            "id": "server_constant_no_binding.default",
            "artifact_id": "server_constant_no_binding",
            "artifact_version": 1,
            "bindings": {},
        }
    )
    run_result = await api.run_deployment(
        deployment_id="server_constant_no_binding.default",
        workflow_input={},
    )

    assert artifact_result["required_logical_sources"] == []
    assert deployment_result["deployment_id"] == "server_constant_no_binding.default"
    assert run_result["status"] == "completed"
    assert run_result["output"]["result"] == "hello from server"
```

If the exact response shape differs, follow the current assertions in
`test_local_static_server_runs_deployment_and_persists_run`. The only intended
behavioral difference is no artifact source binding and no deployment binding.

- [ ] **Step 2: Run tests and fix plan shape if needed**

Run:

```bash
uv run pytest tests/wf_server/test_local_static_server.py::test_local_static_wf_std_deployment_runs_without_source_binding -q
```

Expected: passes after platform validation changes. If it fails due plan shape, adapt the test to an existing local-static helper workflow; do not change product code unless the failure is `binding_missing`.

- [ ] **Step 3: Update roadmap**

In `docs/current_roadmap.md`, replace the platform-source next-design note with:

```markdown
- Completed platform source policy: `wf.*` process-provided sources are marked
  as platform sources and no longer require self-bindings such as
  `wf.std=wf.std` in deployments.
```

Keep the `wf.source` source-ref helper note as next design work.

- [ ] **Step 4: Final verification and commit**

Run:

```bash
uv run pytest tests/platform/test_sources.py tests/artifacts/test_validation.py tests/wf_api/test_artifact_api.py tests/wf_server/test_local_static_server.py tests/wf_transport_rpc_http/test_app.py -q
uv run ruff check src/wf_platform src/wf_artifacts src/wf_api tests/platform tests/artifacts tests/wf_api/test_artifact_api.py tests/wf_server/test_local_static_server.py tests/wf_transport_rpc_http/test_app.py
uv run basedpyright --level error src/wf_platform src/wf_artifacts src/wf_api tests/platform tests/artifacts tests/wf_api/test_artifact_api.py tests/wf_server/test_local_static_server.py tests/wf_transport_rpc_http/test_app.py
```

Expected: focused tests pass, ruff clean, typecheck 0 errors.

Commit:

```bash
git add tests/wf_server/test_local_static_server.py docs/current_roadmap.md
git commit -m "test: prove platform sources need no bindings"
```

---

## Self-Review

- Spec coverage: plan adds metadata/policy, marks platform sources, updates validation, removes binding UX prompts, and proves `wf.std` works without self-binding.
- Placeholder scan: no TBD/TODO/fill-in placeholders remain.
- Type consistency: the field is `CapabilitySource.policy`, snapshot is `SourcePolicySnapshot`, and validation uses `AvailableSource.platform`.
