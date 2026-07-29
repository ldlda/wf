# Safe Compatibility Merges Implementation Plan

**Status:** Completed

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent compatibility-map merges from silently changing canonical step and workflow-output bindings.

**Architecture:** Keep the existing map operations, but add semantic preflight in `WorkflowDraftApi` before any patch. Step maps must round-trip their existing canonical lists exactly; workflow-output maps reject only requested sources that identify more than one existing binding.

**Tech Stack:** Python 3.14, Pydantic draft models, revisioned draft workspace store, pytest, Typer.

## Global Constraints

- Preserve canonical ordered binding lists as the source of truth.
- Reject unsafe compatibility merges before mutation.
- Preserve simple representable `--merge` behavior.
- Do not add a new binding model or change runtime binding semantics.
- Stale revision conflicts must win after request-envelope validation.
- Use focused pytest commands before broad verification.

---

### Task 1: Guard Step Input Compatibility Merges

**Files:**
- Modify: `src/wf_api/drafts.py`
- Modify: `src/wf_api/draft_authoring.py`
- Test: `tests/wf_api/test_drafts_service.py`

**Interfaces:**
- Produces: `WorkflowDraftApi._workspace_if_revision_matches`
- Produces: `_require_lossless_step_input_map_round_trip(payload, *, step_id)`
- Preserves: `WorkflowDraftApi.set_step_input_map`

- [x] **Step 1: Write failing tests for lossless and lossy input merges**

Add focused tests beside
`test_step_map_helpers_merge_with_existing_bindings`:

```python
@pytest.mark.asyncio
async def test_step_input_map_merge_rejects_canonical_source_fan_out(
    tmp_path: Path,
) -> None:
    api, _service, authoring = _draft_api(
        FileWorkflowArtifactStore(tmp_path / "input_merge_fan_out"),
        register_echo=True,
    )
    await api.create_draft_workspace(
        workspace_id="report",
        draft=_structured_report_draft(),
    )
    await authoring.set_step_input_bindings(
        workspace_id="report",
        revision=1,
        step_id="report",
        bindings=[
            InputPathBinding(
                path=GraphSourcePath.state("title"),
                target=LocalPath.of("request", "title"),
            ),
            InputPathBinding(
                path=GraphSourcePath.state("title"),
                target=LocalPath.of("audit", "title"),
            ),
        ],
    )
    before = await api.get_draft_workspace(
        workspace_id="report",
        include_draft=True,
    )

    with pytest.raises(ValueError, match="complete canonical binding list"):
        await api.set_step_input_map(
            workspace_id="report",
            revision=2,
            step_id="report",
            input_map={"input.body": "request.body"},
            merge=True,
        )

    after = await api.get_draft_workspace(
        workspace_id="report",
        include_draft=True,
    )
    assert after == before
```

Add a second rejection test with a path binding before a literal binding,
proving the compatibility serializer cannot move that literal to its normal
literal-prefix position. Keep the existing simple merge test as the positive
representable case.

Add a stale-revision test where the draft contains fan-out but the request uses
an old revision. Assert a conflict payload, not the lossless-merge `ValueError`.

- [x] **Step 2: Run the focused tests and verify RED**

Run:

```bash
uv run pytest tests/wf_api/test_drafts_service.py -k "step_input_map_merge" -q
```

Expected: the fan-out and interleaving tests fail because the merge succeeds or
rewrites the list; the stale-revision test fails if preflight runs first.

- [x] **Step 3: Add the revision preflight and exact round-trip guard**

In `WorkflowDraftApi`, add:

```python
def _workspace_if_revision_matches(
    self,
    *,
    workspace_id: str,
    revision: int,
) -> WorkflowDraftWorkspace | dict[str, Any]:
    """Load one workspace or return its canonical revision-conflict payload."""
```

Use the same summary/diagnostic shape already produced by
`WorkflowDraftAuthoringApi._workspace_if_revision_matches`. Refactor that
authoring helper to delegate to `self.drafts._workspace_if_revision_matches`
instead of maintaining two conflict implementations.

Add a module helper:

```python
def _require_lossless_step_input_map_round_trip(
    payload: object,
    *,
    step_id: str,
) -> tuple[dict[str, str], dict[str, Any]]:
    """Return compatibility maps only when they reproduce the binding list."""
    input_map, input_values = _input_maps_from_payload(payload)
    rebuilt = _draft_input_bindings_payload(input_map, input_values)
    if rebuilt != payload:
        raise ValueError(
            f"step {step_id!r} inputs cannot be safely merged through a "
            "compatibility map; replace the complete canonical binding list instead"
        )
    return input_map, input_values
```

Update `set_step_input_map` so `merge=True`:

1. calls `_workspace_if_revision_matches`;
2. immediately returns a conflict payload when stale;
3. reads the selected step from that workspace;
4. calls the round-trip guard;
5. overlays the requested map;
6. delegates the final mutation to `patch_draft_workspace`.

Do not run the guard for replacement mode (`merge=False`).

- [x] **Step 4: Run focused tests and verify GREEN**

Run:

```bash
uv run pytest tests/wf_api/test_drafts_service.py -k "step_input_map_merge or step_map_helpers_merge" -q
```

Expected: all selected tests pass.

- [x] **Step 5: Commit Task 1**

```bash
git add src/wf_api/drafts.py src/wf_api/draft_authoring.py tests/wf_api/test_drafts_service.py
git commit -m "fix: reject lossy step input map merges"
```

### Task 2: Guard Step Output And Workflow Output Merges

**Files:**
- Modify: `src/wf_api/drafts.py`
- Test: `tests/wf_api/test_drafts_service.py`

**Interfaces:**
- Produces: `_require_lossless_step_output_map_round_trip(payload, *, step_id)`
- Preserves: `WorkflowDraftApi.set_step_output_map`
- Preserves: `WorkflowDraftApi.set_workflow_output_map`

- [x] **Step 1: Write failing step-output fan-out tests**

Create a draft whose step output contains:

```python
[
    {"source": "report.title", "target": "state.report.title"},
    {"source": "report.title", "target": "state.audit.title"},
]
```

Call:

```python
await api.set_step_output_map(
    workspace_id="report",
    revision=2,
    step_id="report",
    output_map={"rendered": "state.rendered"},
    merge=True,
)
```

with an unrelated new mapping.
Assert `ValueError` contains `complete canonical binding list`, then assert the
full workspace and revision remain unchanged.

Add a stale-revision variant and retain the existing unique-source merge test as
the positive case.

- [x] **Step 2: Write failing workflow-output ambiguity tests**

Create workflow output bindings:

```python
[
    {"path": "state.title", "target": "report.title"},
    {"path": "state.title", "target": "audit.title"},
    {"value": "markdown", "target": "format"},
]
```

Add two tests:

1. merging `{"state.title": "renamed"}` rejects and does not mutate;
2. merging `{"state.other": "other"}` succeeds while preserving both
   `state.title` bindings, the literal, and their order.

- [x] **Step 3: Run focused tests and verify RED**

Run:

```bash
uv run pytest tests/wf_api/test_drafts_service.py -k "step_output_map_merge or workflow_output_map_merge" -q
```

Expected: fan-out step output is collapsed and the ambiguous workflow-output
source updates multiple bindings.

- [x] **Step 4: Implement minimal guards**

Add:

```python
def _require_lossless_step_output_map_round_trip(
    payload: object,
    *,
    step_id: str,
) -> dict[str, str]:
    """Return a compatibility map only when it reproduces the output list."""
    output_map = _output_map_from_payload(payload)
    rebuilt = _draft_output_bindings_payload(output_map)
    if rebuilt != payload:
        raise ValueError(
            f"step {step_id!r} outputs cannot be safely merged through a "
            "compatibility map; replace the complete canonical binding list instead"
        )
    return output_map
```

Apply the same revision-first ordering used by Task 1.

For workflow outputs, count existing path bindings only for keys in the
requested `output_map`. Before constructing the merged list, reject a source
whose count is greater than one:

```python
ambiguous = next(
    (
        source
        for source in output_map
        if sum(
            1
            for binding in output_payload
            if isinstance(binding, dict) and binding.get("path") == source
        )
        > 1
    ),
    None,
)
if ambiguous is not None:
    raise ValueError(
        f"workflow output source {ambiguous!r} has multiple bindings and "
        "cannot be updated through a compatibility map; replace the complete "
        "canonical binding list instead"
    )
```

Leave unrequested duplicate sources and literal records untouched.

- [x] **Step 5: Run focused and API regression tests**

Run:

```bash
uv run pytest tests/wf_api/test_drafts_service.py -k "map_helpers or set_step_input_map or set_step_output_map or set_workflow_output_map" -q
```

Expected: all selected tests pass.

- [x] **Step 6: Commit Task 2**

```bash
git add src/wf_api/drafts.py tests/wf_api/test_drafts_service.py
git commit -m "fix: reject ambiguous output map merges"
```

### Task 3: Align CLI Guidance, Issues, And Verification

**Files:**
- Modify: `src/wf_cli/commands/drafts.py`
- Modify: `tests/wf_cli/test_app.py`
- Modify: `ISSUES.md`

**Interfaces:**
- Consumes: compatibility merge errors from Tasks 1-2
- Produces: CLI help that describes rejection rather than acceptable loss

- [x] **Step 1: Write the failing CLI help assertion**

Update `test_wf_draft_map_help_explains_replace_merge_and_validate` to require:

```python
assert "rejects existing bindings that cannot round-trip safely" in input_help
assert "replace the complete canonical binding list" in output_help
assert "ambiguous fan-out sources" in workflow_output_help
```

Remove assertions that describe compatibility merge as merely
`potentially lossy`.

- [x] **Step 2: Run the CLI help test and verify RED**

Run:

```bash
uv run pytest tests/wf_cli/test_app.py::test_wf_draft_map_help_explains_replace_merge_and_validate -q
```

Expected: FAIL because current help still says `potentially lossy`.

- [x] **Step 3: Update command help and issue state**

Revise the `set-input`, `set-output`, and `set-workflow-output` docstrings and
`--merge` help text. State that merge:

- is compatibility-only;
- preserves simple map-shaped bindings;
- rejects canonical lists it cannot reproduce;
- requires canonical replacement for fan-out or ambiguous records.

Mark the `ISSUES.md` compatibility step map item complete and summarize the
guarded behavior without claiming the map representation gained fan-out.

- [x] **Step 4: Run focused verification**

Run:

```bash
uv run pytest tests/wf_api/test_drafts_service.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py -q
uv run ruff check src/wf_api/drafts.py src/wf_api/draft_authoring.py src/wf_cli/commands/drafts.py tests/wf_api/test_drafts_service.py tests/wf_cli/test_app.py
uv run basedpyright --level error src/wf_api src/wf_cli
git diff --check
```

Expected: tests pass, Ruff reports no issues, basedpyright reports zero errors,
and `git diff --check` emits no errors.

- [x] **Step 5: Commit Task 3**

```bash
git add src/wf_cli/commands/drafts.py tests/wf_cli/test_app.py ISSUES.md
git commit -m "docs: explain safe compatibility merges"
```

## Post-Review Hardening

The final review found that `bind_draft` still reconstructed canonical input
and output lists through compatibility maps. The completed slice therefore
also updates focused binds directly on typed canonical lists, preserving
unrelated fan-out, literals, and ordering while rejecting ambiguous requested
sources before mutation. Remote CLI regressions cover canonical-replacement
guidance for step inputs, step outputs, and workflow outputs.
