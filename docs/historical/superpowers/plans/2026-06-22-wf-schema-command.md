# `wf schema` Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the uncommitted `wf schema` prototype with a catalog-backed command that emits compact JSON outlines by default and valid self-contained JSON Schema with `--verbose`.

**Architecture:** Pydantic `TypeAdapter.json_schema()` remains the only schema generator. A focused `wf_cli.schema_catalog` module indexes root schemas and Pydantic `$defs`, projects a bounded non-validating outline, and wraps component definitions in a complete verbose document. The Typer command is a thin JSON-emitting adapter with aliases, catalog listing, and nonzero errors.

**Tech Stack:** Python 3.14, Pydantic v2 `TypeAdapter`, `jsonschema.Draft202012Validator`, Typer, pytest.

---

## File Structure

- Create `src/wf_cli/schema_catalog.py`: schema generation, catalog indexing,
  compact projection, and verbose document construction.
- Replace `src/wf_cli/commands/schema.py`: thin Typer command.
- Modify `src/wf_cli/app.py`: register optional-argument schema command without
  forced help on no arguments.
- Create `tests/wf_cli/test_schema.py`: focused catalog/CLI behavior.
- Modify `tests/wf_cli/test_app.py`: remove stale WIP assertion.
- Modify `skills/wf-cli/SKILL.md`: document the usable public schema surface.
- Modify `skills/wf-workflow/references/direct-plan-import.md`: point raw-plan
  authors to schema discovery.
- Modify `skills/wf-workflow/references/draft-workspaces.md`: point draft
  authors to schema discovery.
- Modify `pyproject.toml` and `uv.lock`: remove the prototype-only `cachetools`
  dependency.

### Task 1: Lock CLI Behavior With Failing Tests

**Files:**
- Create: `tests/wf_cli/test_schema.py`
- Modify: `tests/wf_cli/test_app.py:82-88`

- [ ] **Step 1: Replace the stale WIP test**

Replace `test_wf_schema_help_marks_command_group_as_wip` with:

```python
def test_wf_schema_help_describes_catalog_and_verbose_output() -> None:
    result = runner.invoke(app, ["schema", "--help"])

    assert result.exit_code == 0
    output = result.output.lower()
    assert "compact workflow schema outline" in output
    assert "--verbose" in output
    assert "draft" in output
    assert "raw" in output
    assert "core" in output
```

- [ ] **Step 2: Add catalog, compact, verbose, and error tests**

Create `tests/wf_cli/test_schema.py`:

```python
from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from jsonschema import Draft202012Validator
from typer.testing import CliRunner

from wf_cli.app import app


runner = CliRunner()


def _json_result(*args: str) -> dict[str, Any]:
    result = runner.invoke(app, ["schema", *args])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert isinstance(payload, dict)
    return payload


def _local_refs(value: object) -> Iterator[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "$ref" and isinstance(item, str) and item.startswith("#/$defs/"):
                yield item.removeprefix("#/$defs/")
            else:
                yield from _local_refs(item)
    elif isinstance(value, list):
        for item in value:
            yield from _local_refs(item)


def test_schema_without_name_lists_sorted_catalog() -> None:
    payload = _json_result()
    listed = _json_result("list")

    assert payload == listed
    names = [entry["name"] for entry in payload["schemas"]]
    assert names == sorted(names)
    assert {"WorkflowDraft", "RawWorkflowPlan", "Workflow", "NodeUse"} <= set(names)
    aliases = {
        alias: entry["name"]
        for entry in payload["schemas"]
        for alias in entry["aliases"]
    }
    assert aliases == {
        "core": "Workflow",
        "draft": "WorkflowDraft",
        "raw": "RawWorkflowPlan",
    }


def test_schema_compact_alias_is_json_outline_without_refs() -> None:
    payload = _json_result("raw")

    assert payload["name"] == "RawWorkflowPlan"
    assert payload["kind"] == "schema_outline"
    assert payload["properties"]["nodes"]["items"]["one_of"] == [
        "NodeUse",
        "SubgraphNode",
        "ConditionNode",
        "ForeachNode",
        "JoinNode",
        "EndNode",
        "InterruptNode",
    ]
    assert "$ref" not in json.dumps(payload)
    assert "NodeUse" in payload["related"]
    assert payload["full_schema_command"] == "wf schema raw --verbose"


def test_schema_compact_component_is_queryable() -> None:
    payload = _json_result("NodeUse")

    assert payload["name"] == "NodeUse"
    assert payload["properties"]["input"]["items"]["one_of"] == [
        "InputPathBinding",
        "InputValueBinding",
    ]
    assert "$ref" not in json.dumps(payload)


def test_schema_verbose_root_is_valid_json_schema() -> None:
    payload = _json_result("raw", "--verbose")

    Draft202012Validator.check_schema(payload)
    definitions = payload.get("$defs", {})
    assert set(_local_refs(payload)) <= set(definitions)
    assert payload["title"] == "RawWorkflowPlan"


def test_schema_verbose_component_is_self_contained() -> None:
    payload = _json_result("NodeUse", "--verbose")

    Draft202012Validator.check_schema(payload)
    assert payload["$ref"] == "#/$defs/NodeUse"
    definitions = payload["$defs"]
    assert set(_local_refs(payload)) <= set(definitions)
    Draft202012Validator(payload).validate(
        {"id": "call", "type": "node", "node": "local.report.read_notes"}
    )


def test_schema_unknown_name_fails_with_suggestion() -> None:
    result = runner.invoke(app, ["schema", "Node"])

    assert result.exit_code != 0
    assert "unknown schema 'Node'" in result.output
    assert "NodeUse" in result.output
```

- [ ] **Step 3: Run tests to verify the prototype fails**

Run:

```powershell
uv run pytest tests/wf_cli/test_schema.py tests/wf_cli/test_app.py -q
```

Expected: failures because output is Python repr, catalog listing is absent,
component verbose output is incomplete, unknown names return zero, and the old
help text was removed without replacement tests.

- [ ] **Step 4: Commit the red tests**

```powershell
git add tests/wf_cli/test_schema.py tests/wf_cli/test_app.py
git commit -m "test: define wf schema command contract"
```

### Task 2: Build The Pydantic-Backed Schema Catalog

**Files:**
- Create: `src/wf_cli/schema_catalog.py`
- Test: `tests/wf_cli/test_schema.py`

- [ ] **Step 1: Add catalog unit coverage**

Append:

```python
from wf_cli.schema_catalog import schema_catalog


def test_schema_catalog_resolves_aliases_and_components() -> None:
    catalog = schema_catalog()

    assert catalog.resolve("raw") == "RawWorkflowPlan"
    assert catalog.resolve("RawWorkflowPlan") == "RawWorkflowPlan"
    assert catalog.resolve("NodeUse") == "NodeUse"
    assert catalog.entry("draft").kind == "root"
    assert catalog.entry("NodeUse").kind == "definition"
```

- [ ] **Step 2: Run the catalog test and confirm it fails**

```powershell
uv run pytest tests/wf_cli/test_schema.py::test_schema_catalog_resolves_aliases_and_components -q
```

Expected: import failure for `wf_cli.schema_catalog`.

- [ ] **Step 3: Implement catalog construction**

Create `src/wf_cli/schema_catalog.py` with these public types and functions:

```python
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from difflib import get_close_matches
from functools import cache
from typing import Any, TypeAlias

from jsonschema import Draft202012Validator
from pydantic import TypeAdapter

from wf_api.models import RawWorkflowPlan
from wf_artifacts.drafts.models import WorkflowDraft
from wf_core.models.workflow import Workflow


JsonObject: TypeAlias = dict[str, Any]
SCHEMA_DIALECT = Draft202012Validator.META_SCHEMA["$id"]
ROOT_MODELS: dict[str, type[Any]] = {
    "WorkflowDraft": WorkflowDraft,
    "RawWorkflowPlan": RawWorkflowPlan,
    "Workflow": Workflow,
}
ALIASES = {
    "draft": "WorkflowDraft",
    "raw": "RawWorkflowPlan",
    "core": "Workflow",
}


@dataclass(frozen=True, slots=True)
class SchemaEntry:
    name: str
    aliases: tuple[str, ...]
    kind: str
    description: str | None


@dataclass(frozen=True, slots=True)
class SchemaCatalog:
    roots: dict[str, JsonObject]
    definitions: dict[str, JsonObject]
    aliases: dict[str, str]

    def resolve(self, name: str) -> str:
        canonical = self.aliases.get(name, name)
        if canonical in self.roots or canonical in self.definitions:
            return canonical
        choices = sorted({*self.aliases, *self.roots, *self.definitions})
        suggestion = get_close_matches(name, choices, n=1)
        message = f"unknown schema {name!r}"
        if suggestion:
            message += f". Did you mean {suggestion[0]!r}?"
        raise KeyError(message)

    def schema(self, name: str) -> JsonObject:
        canonical = self.resolve(name)
        source = self.roots.get(canonical, self.definitions.get(canonical))
        if source is None:  # defensive: resolve already checked this
            raise KeyError(canonical)
        return deepcopy(source)

    def entry(self, name: str) -> SchemaEntry:
        canonical = self.resolve(name)
        schema = self.schema(canonical)
        aliases = tuple(sorted(alias for alias, target in self.aliases.items() if target == canonical))
        return SchemaEntry(
            name=canonical,
            aliases=aliases,
            kind="root" if canonical in self.roots else "definition",
            description=schema.get("description"),
        )

    def entries(self) -> list[SchemaEntry]:
        names = sorted({*self.roots, *self.definitions})
        return [self.entry(name) for name in names]


@cache
def schema_catalog() -> SchemaCatalog:
    roots = {
        name: TypeAdapter(model).json_schema(mode="validation", by_alias=True)
        for name, model in ROOT_MODELS.items()
    }
    combined = TypeAdapter(WorkflowDraft | RawWorkflowPlan | Workflow).json_schema(
        mode="validation", by_alias=True
    )
    raw_definitions = combined.get("$defs", {})
    if not isinstance(raw_definitions, dict):
        raise RuntimeError("combined workflow schema has no object $defs table")
    definitions = {name: deepcopy(value) for name, value in raw_definitions.items()}
    for root in roots.values():
        root_definitions = root.get("$defs", {})
        if not isinstance(root_definitions, dict):
            raise RuntimeError("workflow root schema has non-object $defs")
        for name, value in root_definitions.items():
            existing = definitions.get(name)
            if existing is not None and existing != value:
                raise RuntimeError(f"conflicting workflow schema definition: {name}")
            definitions.setdefault(name, deepcopy(value))
    return SchemaCatalog(roots=roots, definitions=definitions, aliases=dict(ALIASES))
```

- [ ] **Step 4: Run catalog tests**

```powershell
uv run pytest tests/wf_cli/test_schema.py::test_schema_catalog_resolves_aliases_and_components -q
```

Expected: pass.

- [ ] **Step 5: Commit the catalog**

```powershell
git add src/wf_cli/schema_catalog.py tests/wf_cli/test_schema.py
git commit -m "feat: add workflow schema catalog"
```

### Task 3: Implement Compact Outlines And Verbose Documents

**Files:**
- Modify: `src/wf_cli/schema_catalog.py`
- Test: `tests/wf_cli/test_schema.py`

- [ ] **Step 1: Add projection and verbose helper tests**

Append:

```python
from wf_cli.schema_catalog import compact_schema_outline, verbose_schema_document


def test_compact_outline_replaces_local_refs_with_names() -> None:
    payload = compact_schema_outline("NodeUse")

    assert payload["properties"]["input"]["items"]["one_of"] == [
        "InputPathBinding",
        "InputValueBinding",
    ]
    assert "$ref" not in json.dumps(payload)


def test_verbose_component_uses_generated_definitions() -> None:
    payload = verbose_schema_document("NodeUse")

    assert payload["$schema"] == Draft202012Validator.META_SCHEMA["$id"]
    assert payload["$ref"] == "#/$defs/NodeUse"
    assert "InputPathBinding" in payload["$defs"]
```

- [ ] **Step 2: Run and confirm helper tests fail**

```powershell
uv run pytest tests/wf_cli/test_schema.py -k "compact_outline or verbose_component_uses" -q
```

Expected: import failures for the helpers.

- [ ] **Step 3: Add compact projection**

Append to `schema_catalog.py`:

```python
PRESENTATION_KEYS = (
    "type",
    "description",
    "default",
    "enum",
    "const",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "minLength",
    "maxLength",
    "minItems",
    "maxItems",
)


def _ref_name(ref: str) -> str:
    prefix = "#/$defs/"
    if not ref.startswith(prefix):
        return ref
    return ref.removeprefix(prefix)


def _compact_node(schema: object, related: set[str]) -> object:
    if not isinstance(schema, dict):
        return deepcopy(schema)
    ref = schema.get("$ref")
    if isinstance(ref, str):
        name = _ref_name(ref)
        if name != ref:
            related.add(name)
        return name

    result: JsonObject = {}
    for key in PRESENTATION_KEYS:
        if key in schema:
            result[key] = deepcopy(schema[key])
    required = schema.get("required")
    if isinstance(required, list):
        result["required"] = deepcopy(required)
    properties = schema.get("properties")
    if isinstance(properties, dict):
        result["properties"] = {
            name: _compact_node(value, related)
            for name, value in properties.items()
        }
    if "items" in schema:
        result["items"] = _compact_node(schema["items"], related)
    for source_key in ("oneOf", "anyOf"):
        branches = schema.get(source_key)
        if not isinstance(branches, list):
            continue
        result["one_of"] = [_compact_node(branch, related) for branch in branches]
        break
    discriminator = schema.get("discriminator")
    if isinstance(discriminator, dict) and isinstance(discriminator.get("propertyName"), str):
        result["discriminator"] = discriminator["propertyName"]
    return result


def compact_schema_outline(name: str) -> JsonObject:
    catalog = schema_catalog()
    canonical = catalog.resolve(name)
    schema = catalog.schema(canonical)
    related: set[str] = set()
    body = _compact_node(schema, related)
    if not isinstance(body, dict):
        body = {"schema": body}
    return {
        "name": canonical,
        "kind": "schema_outline",
        **body,
        "related": sorted(related - {canonical}),
        "full_schema_command": f"wf schema {name} --verbose",
    }
```

- [ ] **Step 4: Add verbose document construction**

Append:

```python
def verbose_schema_document(name: str) -> JsonObject:
    catalog = schema_catalog()
    canonical = catalog.resolve(name)
    if canonical in catalog.roots:
        document = catalog.schema(canonical)
        document.setdefault("$schema", SCHEMA_DIALECT)
    else:
        document = {
            "$schema": SCHEMA_DIALECT,
            "$ref": f"#/$defs/{canonical}",
            "$defs": deepcopy(catalog.definitions),
        }
    Draft202012Validator.check_schema(document)
    return document


def schema_catalog_payload() -> JsonObject:
    return {
        "schemas": [
            {
                "name": entry.name,
                "aliases": list(entry.aliases),
                "kind": entry.kind,
                "description": entry.description,
            }
            for entry in schema_catalog().entries()
        ]
    }
```

- [ ] **Step 5: Run helper tests**

```powershell
uv run pytest tests/wf_cli/test_schema.py -k "compact or verbose or catalog" -q
```

Expected: helper-level tests pass; CLI tests may still fail until Task 4.

- [ ] **Step 6: Commit projection helpers**

```powershell
git add src/wf_cli/schema_catalog.py tests/wf_cli/test_schema.py
git commit -m "feat: project compact and verbose workflow schemas"
```

### Task 4: Wire The Typer Command

**Files:**
- Replace: `src/wf_cli/commands/schema.py`
- Modify: `src/wf_cli/app.py:79-84`
- Test: `tests/wf_cli/test_schema.py`
- Test: `tests/wf_cli/test_app.py`

- [ ] **Step 1: Replace the prototype command**

Replace `src/wf_cli/commands/schema.py` with:

```python
from __future__ import annotations

import typer

from wf_cli.io import emit_json
from wf_cli.schema_catalog import (
    compact_schema_outline,
    schema_catalog,
    schema_catalog_payload,
    verbose_schema_document,
)


def schema_command(
    name: str | None = typer.Argument(
        None,
        help="Schema name or alias. Omit it, or use `list`, to list names.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Print complete valid JSON Schema; output may be large.",
    ),
) -> None:
    """Print a compact workflow schema outline or full JSON Schema."""
    if name is None or name == "list":
        emit_json(schema_catalog_payload())
        return
    try:
        schema_catalog().resolve(name)
    except KeyError as exc:
        message = exc.args[0] if exc.args else str(exc)
        raise typer.BadParameter(message, param_hint="NAME") from exc
    emit_json(
        verbose_schema_document(name)
        if verbose
        else compact_schema_outline(name)
    )
```

- [ ] **Step 2: Register no-argument catalog behavior**

In `src/wf_cli/app.py`, use:

```python
app.command("schema")(schema.schema_command)
```

Do not pass `no_args_is_help=True`; no arguments now list the catalog.

- [ ] **Step 3: Run focused CLI tests**

```powershell
uv run pytest tests/wf_cli/test_schema.py tests/wf_cli/test_app.py -q
```

Expected: all pass.

- [ ] **Step 4: Smoke the real command**

```powershell
uv run wf schema
uv run wf schema raw
uv run wf schema NodeUse
uv run wf schema raw --verbose
uv run wf schema Node
```

Expected: first four print JSON; final command exits nonzero and suggests
`NodeUse`.

- [ ] **Step 5: Commit CLI wiring**

```powershell
git add src/wf_cli/commands/schema.py src/wf_cli/app.py tests/wf_cli/test_schema.py tests/wf_cli/test_app.py
git commit -m "feat: expose workflow schema catalog in cli"
```

### Task 5: Remove Prototype Dependency And Update Agent Instructions

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `skills/wf-cli/SKILL.md`
- Modify: `skills/wf-workflow/references/direct-plan-import.md`
- Modify: `skills/wf-workflow/references/draft-workspaces.md`

- [ ] **Step 1: Remove `cachetools`**

Run:

```powershell
uv remove cachetools
```

Expected: `cachetools` disappears from direct project dependencies and lockfile
project metadata. It may remain transitively only if another dependency needs
it.

- [ ] **Step 2: Replace the stale CLI skill rule**

In `skills/wf-cli/SKILL.md`, replace the WIP statement with:

```markdown
- Use `wf schema` to list workflow document/component shapes.
- Use `wf schema draft`, `wf schema raw`, or `wf schema <Component>` for compact
  JSON guidance before authoring.
- Add `--verbose` only when a complete JSON Schema document is required; it may
  be large.
```

- [ ] **Step 3: Add schema discovery to draft and raw-plan references**

Near the top of `direct-plan-import.md`, add:

```markdown
Before writing a plan, inspect the current public shape:

    wf schema raw
    wf schema NodeUse
    wf schema InputPathBinding
    wf schema OutputBinding

Use `wf schema raw --verbose` only when the complete validation schema is
required.
```

Near the top of `draft-workspaces.md`, add the equivalent draft commands:

```markdown
Before writing or patching a draft, inspect the current public shape:

    wf schema draft
    wf schema DraftUseStep
```

- [ ] **Step 4: Verify user-facing skills contain no stale WIP statement**

```powershell
rg -n "empty command group|no schema subcommands|do not rely on it" skills
```

Expected: no matches referring to `wf schema`.

- [ ] **Step 5: Run focused verification**

```powershell
uv run pytest tests/wf_cli/test_schema.py tests/wf_cli/test_app.py -q
uv run ruff check src/wf_cli/schema_catalog.py src/wf_cli/commands/schema.py src/wf_cli/app.py tests/wf_cli/test_schema.py tests/wf_cli/test_app.py
uv run ruff format --check src/wf_cli/schema_catalog.py src/wf_cli/commands/schema.py src/wf_cli/app.py tests/wf_cli/test_schema.py tests/wf_cli/test_app.py
uv run basedpyright --level error src/wf_cli/schema_catalog.py src/wf_cli/commands/schema.py src/wf_cli/app.py tests/wf_cli/test_schema.py tests/wf_cli/test_app.py
git diff --check
```

Expected: tests pass, lint/typecheck are clean, and only accepted Windows CRLF
warnings appear from `git diff --check`.

- [ ] **Step 6: Commit dependency/docs cleanup**

```powershell
git add pyproject.toml uv.lock skills/wf-cli/SKILL.md skills/wf-workflow/references/direct-plan-import.md skills/wf-workflow/references/draft-workspaces.md
git commit -m "docs: teach agents workflow schema discovery"
```

### Task 6: Final Review And Plan Archive

**Files:**
- Modify: `docs/current_roadmap.md`
- Move after completion: `docs/superpowers/plans/2026-06-22-wf-schema-command.md` to `docs/historical/superpowers/plans/2026-06-22-wf-schema-command.md`

- [ ] **Step 1: Add the completed roadmap note**

Add under the current product/agent UX milestones:

```markdown
- Completed: `wf schema` now lists workflow document/component models, emits
  compact JSON outlines for agent discovery, and emits valid self-contained
  JSON Schema with `--verbose`.
```

- [ ] **Step 2: Run the complete focused test command once more**

```powershell
uv run pytest tests/wf_cli/test_schema.py tests/wf_cli/test_app.py -q
```

Expected: all pass.

- [ ] **Step 3: Move the completed plan to historical docs**

```powershell
New-Item -ItemType Directory -Force docs/historical/superpowers/plans | Out-Null
Move-Item docs/superpowers/plans/2026-06-22-wf-schema-command.md docs/historical/superpowers/plans/2026-06-22-wf-schema-command.md
```

- [ ] **Step 4: Commit roadmap and archive**

```powershell
git add docs/current_roadmap.md docs/superpowers/plans/2026-06-22-wf-schema-command.md docs/historical/superpowers/plans/2026-06-22-wf-schema-command.md
git commit -m "docs: record wf schema command completion"
```
