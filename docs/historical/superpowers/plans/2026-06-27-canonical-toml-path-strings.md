# Canonical TOML Path Strings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make canonical TOML-key strings the advertised and serialized representation for workflow paths while retaining structured-object input compatibility for existing stored data.

**Architecture:** Keep `GraphSourcePath`, `StatePath`, and `LocalPath` as structured immutable values. Move TOML-key parsing into `wf_core.paths`, add one canonical formatter there, and make every Pydantic path serializer emit strings. `wf_authoring` delegates to the core parser instead of owning a second grammar.

**Tech Stack:** Python 3.14, stdlib `tomllib`, Pydantic v2 core schemas, pytest, Ruff, basedpyright.

---

### Task 1: Define The Core TOML-Key Grammar

**Files:**
- Modify: `src/wf_core/paths.py`
- Test: `tests/core/test_path_values.py`

- [x] **Step 1: Write failing parser and formatter tests**

Add tests proving quoted segments round-trip and roots remain typed:

```python
def test_toml_path_strings_round_trip_literal_segments() -> None:
    source = GraphSourcePath.parse('input."customer.name"."display name"')
    target = StatePath.parse('state."report.title"')
    local = LocalPath.parse('payload."raw.value"')

    assert source.parts == ("customer.name", "display name")
    assert target.parts == ("report.title",)
    assert local.parts == ("payload", "raw.value")
    assert str(source) == 'input."customer.name"."display name"'
    assert str(target) == 'state."report.title"'
    assert str(local) == 'payload."raw.value"'
```

Also test `LocalPath.parse(".")`, bare keys, malformed TOML, invalid roots, and empty writable state paths.

- [x] **Step 2: Run the focused test and verify RED**

Run: `uv run pytest tests/core/test_path_values.py -q`

Expected: quoted full paths fail because current core parsing uses `str.split(".")`.

- [x] **Step 3: Implement shared parsing and formatting**

In `src/wf_core/paths.py`, add the shared implementation:

```python
_BARE_TOML_KEY = re.compile(r"^[A-Za-z0-9_-]+$")


def parse_toml_path_segments(expr: str) -> tuple[str, ...]:
    """Parse a TOML key expression into literal path segments."""
    try:
        parsed = tomllib.loads(f"{expr} = true")
    except tomllib.TOMLDecodeError as exc:
        raise PathResolutionError(
            f"invalid TOML path {expr!r}; quote path segments containing dots or spaces"
        ) from exc

    parts: list[str] = []
    current: object = parsed
    while isinstance(current, dict):
        if len(current) != 1:
            raise PathResolutionError(f"invalid TOML path {expr!r}")
        key, current = next(iter(current.items()))
        parts.append(_validate_segment(key, path_kind="TOML path"))
    if current is not True or not parts:
        raise PathResolutionError(f"invalid TOML path {expr!r}")
    return tuple(parts)


def format_toml_path_segments(parts: tuple[str, ...]) -> str:
    """Format literal segments as one canonical TOML key expression."""
    if not parts:
        raise PathResolutionError("cannot format an empty TOML path")
    return ".".join(
        part
        if _BARE_TOML_KEY.fullmatch(part)
        else json.dumps(part, ensure_ascii=False)
        for part in parts
    )
```

Use `tomllib.loads(f"{expr} = true")` for parsing. The formatter emits bare
TOML keys when legal and quoted TOML basic strings otherwise. Keep the local
root marker `.` as a special complete path, not a TOML key expression.

Update:

```python
GraphSourcePath.parse(raw)
GraphSourcePath.__str__()
StatePath.parse(raw)
StatePath.__str__()
LocalPath.parse(raw)
LocalPath.__str__()
```

`GraphSourcePath.parse` parses the whole expression, then treats the first
segment as the graph root. `StatePath` requires root `state` plus at least one
remaining segment. `LocalPath` has no serialized `local.` prefix.

- [x] **Step 4: Run focused core tests**

Run: `uv run pytest tests/core/test_path_values.py tests/core/test_nested_state_paths.py -q`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/wf_core/paths.py tests/core/test_path_values.py
git commit -m "feat: define canonical TOML workflow paths"
```

### Task 2: Serialize Paths As Strings And Advertise Strings In JSON Schema

**Files:**
- Modify: `src/wf_core/paths.py`
- Modify: `tests/core/test_path_values.py`
- Modify: `tests/core/test_canonical_node_bindings.py`

- [x] **Step 1: Write failing Pydantic projection tests**

Extend the existing Pydantic path payload test:

```python
def test_path_models_serialize_strings_but_accept_structural_compat() -> None:
    payload = PathPayload.model_validate(
        {
            "source": {"root": "input", "parts": ["user.name"]},
            "target": {"root": "state", "parts": ["person name"]},
            "local": {"root": "local", "parts": ["payload.text"]},
        }
    )

    assert payload.model_dump(mode="json") == {
        "source": 'input."user.name"',
        "target": 'state."person name"',
        "local": '"payload.text"',
    }
    assert PathPayload.model_json_schema()["properties"]["source"]["type"] == "string"
```

- [x] **Step 2: Run tests and verify RED**

Run: `uv run pytest tests/core/test_path_values.py tests/core/test_canonical_node_bindings.py -q`

Expected: current serializers emit `{root, parts}` objects.

- [x] **Step 3: Change serializers and JSON schemas**

Make each path `_serialize` return `str(value)`. Replace the structural
`_path_json_schema` with a string schema whose description documents TOML-key
quoting. Do not include the compatibility object in generated JSON Schema;
validators continue accepting it so old persisted records remain readable.

Keep a comment at the validator seam:

```python
# Structural objects remain input-only compatibility for persisted records.
# New schemas and serializers expose the canonical TOML-key string form.
```

- [x] **Step 4: Update exact serialized binding expectations**

Adjust tests that assert JSON payloads to expect strings such as
`input.message`, `state.echoed`, and `.`. Keep field-level assertions rather
than replacing whole large snapshots.

- [x] **Step 5: Run core serialization tests**

Run: `uv run pytest tests/core/test_path_values.py tests/core/test_canonical_node_bindings.py tests/core/test_run_codec.py -q`

Expected: PASS, including decoding old structural path objects.

- [x] **Step 6: Commit**

```bash
git add src/wf_core/paths.py tests/core/test_path_values.py tests/core/test_canonical_node_bindings.py
git commit -m "feat: serialize canonical workflow path strings"
```

### Task 3: Remove The Duplicate Authoring Parser

**Files:**
- Modify: `src/wf_authoring/dsl/path_inputs.py`
- Modify: `tests/authoring/test_path_inputs.py`

- [x] **Step 1: Add delegation coverage**

Add a test proving full rooted strings and explicit-root expressions resolve to
the same structured value:

```python
def test_authoring_paths_share_core_toml_grammar() -> None:
    assert coerce_graph_path('state."person.name"') == GraphSourcePath(
        "state", ("person.name",)
    )
    assert coerce_graph_path('"person.name"', root="state") == GraphSourcePath(
        "state", ("person.name",)
    )
```

- [x] **Step 2: Replace `_parse_toml_key_expr`**

Delete the local `tomllib` parser and import
`parse_toml_path_segments` from `wf_core.paths`. Preserve iterable and
structural-object coercion behavior for Python callers.

- [x] **Step 3: Run authoring tests**

Run: `uv run pytest tests/authoring/test_path_inputs.py tests/authoring/test_builder.py tests/authoring/test_conditions.py -q`

Expected: PASS.

- [x] **Step 4: Commit**

```bash
git add src/wf_authoring/dsl/path_inputs.py tests/authoring/test_path_inputs.py
git commit -m "refactor: share workflow path grammar"
```

### Task 4: Update Draft, Transport, And Compatibility Coverage

**Files:**
- Modify: `tests/wf_api/test_drafts_service.py`
- Modify: `tests/wf_transport_rpc_http/test_app.py`
- Modify: `tests/wf_transport_rpc_http/test_client.py`
- Modify: `tests/wf_mcp/workflow_surface/test_drafts.py`

- [x] **Step 1: Add one stored-draft compatibility regression**

Create a workspace from a draft containing structural path objects, retrieve or
patch it, and assert the next serialized draft uses canonical strings while
preserving the same path values.

- [x] **Step 2: Update focused transport assertions**

Change only assertions for serialized path fields. RPC and MCP requests should
advertise and return strings; input model tests must still accept structural
objects.

- [x] **Step 3: Run affected suites**

Run:

```bash
uv run pytest tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_mcp/workflow_surface/test_drafts.py -q
```

Expected: PASS.

- [x] **Step 4: Commit**

```bash
git add tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_mcp/workflow_surface/test_drafts.py
git commit -m "test: cover canonical path transport compatibility"
```

### Task 5: Documentation And Final Verification

**Files:**
- Modify: `docs/workflow_drafts.md`
- Modify: `docs/wf_authoring_control_flow.md`
- Modify: `skills/wf-cli/SKILL.md`
- Modify: `skills/wf-workflow/references/draft-workspaces.md`
- Modify: `skills/wf-workflow/references/direct-plan-import.md`
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-27-draft-semantic-authoring-boundary.md`
- Move after completion: `docs/superpowers/plans/2026-06-27-canonical-toml-path-strings.md` -> `docs/historical/superpowers/plans/2026-06-27-canonical-toml-path-strings.md`

- [x] **Step 1: Replace structural path examples**

Use canonical examples:

```json
{"path":"input.text","target":"text"}
{"source":"result","target":"state.result"}
```

Document TOML quoting with `state."field.with.dot"`. State that structural
objects are input-only compatibility and must not be generated by agents.

- [x] **Step 2: Record implementation status**

Mark the canonical-path section implemented in the design spec and add a short
completed roadmap entry.

- [x] **Step 3: Run verification**

```bash
uv run pytest tests/core/test_path_values.py tests/core/test_canonical_node_bindings.py tests/authoring/test_path_inputs.py tests/authoring/test_builder.py tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_mcp/workflow_surface/test_drafts.py -q
uv run ruff check
uv run ruff format --check
uv run basedpyright --level error
git diff --check
```

Expected: all tests pass, Ruff is clean, basedpyright reports zero errors, and
`git diff --check` reports no whitespace errors.

- [x] **Step 4: Archive and commit the plan**

```bash
git mv docs/superpowers/plans/2026-06-27-canonical-toml-path-strings.md docs/historical/superpowers/plans/2026-06-27-canonical-toml-path-strings.md
git add docs skills
git commit -m "docs: document canonical workflow path strings"
```
