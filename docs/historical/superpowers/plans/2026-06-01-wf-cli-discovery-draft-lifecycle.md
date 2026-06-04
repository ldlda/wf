# wf CLI Discovery And Draft Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the minimum CLI authoring loop: discover capabilities, create/patch/validate/save draft workspaces, inspect artifacts, and save/delete deployments.

**Architecture:** Keep CLI commands thin over `WorkflowSurfaceHandlers`; do not duplicate workflow validation or artifact logic. Add one small shared output-format helper for list/discovery commands so `ids` and `compact` output do not get copy-pasted command by command.

**Tech Stack:** Python 3.14, Typer, Pydantic v2 models already used by handlers, existing `wf_cli.context`, existing `wf_cli.io`, pytest `CliRunner`.

---

## Scope

Implement these CLI commands:

```text
wf cap list
wf cap inspect
wf artifact list
wf artifact inspect
wf draft list
wf draft inspect
wf draft create-from-capability
wf draft patch
wf draft validate
wf draft save
wf deploy list
wf deploy inspect
wf deploy save
wf deploy delete
```

Already implemented and not part of this slice:

```text
wf deploy validate
wf run start
wf run inspect
wf run trace
wf explain
```

Do not add targeted draft editing helpers in this slice:

```text
wf draft step add
wf draft route set
wf draft output set
wf draft field add
```

Those are the next ergonomic layer after raw lifecycle coverage is proven.

## Output Contracts

`json` is default everywhere.

List/discovery commands:

```text
wf cap list       --format json|ids|compact
wf artifact list  --format json|ids|compact
wf draft list     --format json|ids|compact
wf deploy list    --format json|ids|compact
```

Details/mutations remain JSON-only:

```text
wf cap inspect
wf artifact inspect
wf draft inspect
wf draft create-from-capability
wf draft patch
wf draft validate
wf draft save
wf deploy inspect
wf deploy save
wf deploy delete
```

Do not implement `table`.

## File Structure

Create:

```text
src/wf_cli/formats.py
tests/wf_cli/test_discovery_lifecycle.py
```

Modify:

```text
src/wf_cli/io.py
src/wf_cli/commands/caps.py
src/wf_cli/commands/artifacts.py
src/wf_cli/commands/drafts.py
src/wf_cli/commands/deployments.py
tests/wf_cli/test_app.py
```

Do not modify:

```text
src/wf_mcp/workflow_surface/handlers.py
src/wf_core/
src/wf_artifacts/
```

If a handler shape is inconvenient, call it as-is and document the CLI limitation in a test or command docstring. Do not add new workflow-surface behavior in this slice.

## Task 1: Shared CLI Format And JSON Value Helpers

**Files:**

- Create: `src/wf_cli/formats.py`
- Modify: `src/wf_cli/io.py`
- Test: `tests/wf_cli/test_discovery_lifecycle.py`

- [ ] **Step 1: Add focused helper tests**

Create `tests/wf_cli/test_discovery_lifecycle.py` with:

```python
from __future__ import annotations

import json

import pytest

from wf_cli.formats import ListOutputFormat, render_list_payload
from wf_cli.io import CliInputError, parse_json_value


def test_render_list_payload_ids_uses_requested_id_field() -> None:
    payload = {"capabilities": [{"name": "wf.std.truthy"}, {"name": "wf.std.add"}]}

    rendered = render_list_payload(
        payload,
        collection_key="capabilities",
        output_format=ListOutputFormat.IDS,
        id_field="name",
    )

    assert rendered == "wf.std.truthy\nwf.std.add"


def test_render_list_payload_compact_includes_summary_fields() -> None:
    payload = {
        "nodes": [
            {
                "name": "workflow.echo.v1",
                "kind": "workflow",
                "display_name": "Echo",
            }
        ]
    }

    rendered = render_list_payload(
        payload,
        collection_key="nodes",
        output_format=ListOutputFormat.COMPACT,
        id_field="name",
        summary_fields=("kind", "display_name"),
    )

    assert rendered == "workflow.echo.v1\tkind=workflow\tdisplay_name=Echo"


def test_render_list_payload_json_returns_pretty_json() -> None:
    payload = {"deployments": [{"id": "echo.personal"}]}

    rendered = render_list_payload(
        payload,
        collection_key="deployments",
        output_format=ListOutputFormat.JSON,
        id_field="id",
    )

    parsed = json.loads(rendered)
    assert parsed["deployments"][0]["id"] == "echo.personal"


def test_parse_json_value_accepts_arrays_for_json_patch() -> None:
    value = parse_json_value(input_json='[{"op":"replace","path":"/name","value":"x"}]', input_file=None)

    assert isinstance(value, list)
    assert value[0]["op"] == "replace"


def test_parse_json_value_rejects_both_input_modes(tmp_path) -> None:
    payload = tmp_path / "payload.json"
    payload.write_text("{}", encoding="utf-8")

    with pytest.raises(CliInputError, match="mutually exclusive"):
        parse_json_value(input_json="{}", input_file=payload)
```

- [ ] **Step 2: Run failing helper tests**

Run:

```bash
uv run pytest tests/wf_cli/test_discovery_lifecycle.py -q
```

Expected: fail because `wf_cli.formats` and `parse_json_value` do not exist.

- [ ] **Step 3: Implement list formatting helper**

Create `src/wf_cli/formats.py`:

```python
from __future__ import annotations

import json
from enum import StrEnum
from typing import Any


class ListOutputFormat(StrEnum):
    """Output formats allowed for list/discovery commands."""

    JSON = "json"
    IDS = "ids"
    COMPACT = "compact"


def render_list_payload(
    payload: dict[str, Any],
    *,
    collection_key: str,
    output_format: ListOutputFormat,
    id_field: str,
    summary_fields: tuple[str, ...] = (),
) -> str:
    """Render a handler list payload without changing the JSON contract."""
    if output_format is ListOutputFormat.JSON:
        return json.dumps(payload, indent=2, sort_keys=True)
    items = payload.get(collection_key, [])
    if not isinstance(items, list):
        raise ValueError(f"list payload missing array field {collection_key!r}")
    if output_format is ListOutputFormat.IDS:
        return "\n".join(_item_id(item, id_field=id_field) for item in items)
    return "\n".join(
        _compact_line(item, id_field=id_field, summary_fields=summary_fields)
        for item in items
    )


def emit_list_payload(
    payload: dict[str, Any],
    *,
    collection_key: str,
    output_format: ListOutputFormat,
    id_field: str,
    summary_fields: tuple[str, ...] = (),
) -> None:
    """Print a list payload in the requested CLI list format."""
    print(
        render_list_payload(
            payload,
            collection_key=collection_key,
            output_format=output_format,
            id_field=id_field,
            summary_fields=summary_fields,
        )
    )


def _item_id(item: object, *, id_field: str) -> str:
    if not isinstance(item, dict):
        return str(item)
    value = item.get(id_field)
    return "" if value is None else str(value)


def _compact_line(
    item: object,
    *,
    id_field: str,
    summary_fields: tuple[str, ...],
) -> str:
    if not isinstance(item, dict):
        return str(item)
    parts = [_item_id(item, id_field=id_field)]
    for field in summary_fields:
        if field in item and item[field] is not None:
            parts.append(f"{field}={item[field]}")
    return "\t".join(parts)
```

- [ ] **Step 4: Add JSON value parser**

Modify `src/wf_cli/io.py`:

```python
def parse_json_value(
    *,
    input_json: str | None,
    input_file: Path | None,
) -> Any:
    """Parse exactly one JSON value from inline JSON or a file path."""
    if input_json is not None and input_file is not None:
        raise CliInputError("--input and --input-file are mutually exclusive")
    if input_json is None and input_file is None:
        raise CliInputError("--input or --input-file is required")
    raw = input_json if input_json is not None else _read_input_file(input_file)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CliInputError(f"invalid JSON input: {exc.msg}") from exc
```

Then simplify `parse_json_input` to call this helper:

```python
def parse_json_input(
    *,
    input_json: str | None,
    input_file: Path | None,
) -> dict[str, Any]:
    """Parse exactly one JSON object from inline JSON or a file path."""
    if input_json is None and input_file is None:
        return {}
    payload = parse_json_value(input_json=input_json, input_file=input_file)
    if not isinstance(payload, dict):
        raise CliInputError("JSON input must be an object")
    return payload
```

- [ ] **Step 5: Run helper tests**

Run:

```bash
uv run pytest tests/wf_cli/test_discovery_lifecycle.py -q
```

Expected: pass.

## Task 2: Capability Discovery Commands

**Files:**

- Modify: `src/wf_cli/commands/caps.py`
- Test: `tests/wf_cli/test_discovery_lifecycle.py`
- Test: `tests/wf_cli/test_app.py`

- [ ] **Step 1: Add capability CLI tests**

Replace the import block at the top of `tests/wf_cli/test_discovery_lifecycle.py`
with the complete import set used by this slice:

```python
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from wf_artifacts import FileWorkflowArtifactStore, WorkflowDeployment
from wf_cli.app import app
from wf_cli.context import CliContext, load_cli_context
from wf_cli.formats import ListOutputFormat, render_list_payload
from wf_cli.io import CliInputError, parse_json_value

from tests.wf_mcp.test_support import echo_tool, local_temp_root
from tests.wf_mcp.workflow_surface.conftest import echo_artifact
```

Then append to `tests/wf_cli/test_discovery_lifecycle.py`:

```python


runner = CliRunner()


def _write_cli_config(root: Path) -> Path:
    config_path = root / "wf_mcp.config.json"
    config_path.write_text(
        json.dumps(
            {
                "store_root": ".wf_mcp_store",
                "connections": [
                    {"id": "demo.personal", "server": "demo", "account": "personal"}
                ],
            }
        ),
        encoding="utf-8",
    )
    return config_path


def _load_cli_context_with_specs(config_path: str | Path) -> CliContext:
    """Seed executable demo specs for CLI tests only.

    Config loading registers connections and stores; it does not register
    in-memory test NodeSpecs. Production source registration remains outside
    this CLI slice.
    """
    context = load_cli_context(config_path)
    context.service.register_specs("demo.personal", echo_tool)
    return context


def test_wf_cap_list_outputs_json() -> None:
    root = local_temp_root() / "wf_cli_cap_list"
    root.mkdir(parents=True, exist_ok=True)
    config_path = _write_cli_config(root)

    with patch("wf_cli.commands.caps.load_cli_context", _load_cli_context_with_specs):
        result = runner.invoke(app, ["--config", str(config_path), "cap", "list", "--source", "demo.personal"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["capabilities"][0]["name"] == "demo.personal.echo_tool"
    assert payload["capabilities"][0]["source_id"] == "demo.personal"


def test_wf_cap_list_ids_format() -> None:
    root = local_temp_root() / "wf_cli_cap_list_ids"
    root.mkdir(parents=True, exist_ok=True)
    config_path = _write_cli_config(root)

    with patch("wf_cli.commands.caps.load_cli_context", _load_cli_context_with_specs):
        result = runner.invoke(app, ["--config", str(config_path), "cap", "list", "--source", "demo.personal", "--format", "ids"])

    assert result.exit_code == 0
    assert result.output.strip() == "demo.personal.echo_tool"


def test_wf_cap_inspect_outputs_detail() -> None:
    root = local_temp_root() / "wf_cli_cap_inspect"
    root.mkdir(parents=True, exist_ok=True)
    config_path = _write_cli_config(root)

    with patch("wf_cli.commands.caps.load_cli_context", _load_cli_context_with_specs):
        result = runner.invoke(app, ["--config", str(config_path), "cap", "inspect", "demo.personal.echo_tool"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["name"] == "demo.personal.echo_tool"
    assert payload["wrapper_hints"]["input_map"] == {"input.text": "text"}
```

Append to `tests/wf_cli/test_app.py`:

```python
def test_wf_cap_list_help_exists() -> None:
    result = runner.invoke(app, ["cap", "list", "--help"])

    assert result.exit_code == 0
    assert "--format" in result.output
    assert "--source" in result.output
```

- [ ] **Step 2: Run capability tests to verify failure**

Run:

```bash
uv run pytest tests/wf_cli/test_discovery_lifecycle.py tests/wf_cli/test_app.py -q
```

Expected: fail because `cap list` and `cap inspect` do not exist.

- [ ] **Step 3: Implement capability commands**

Replace `src/wf_cli/commands/caps.py` with:

```python
from __future__ import annotations

import asyncio
from typing import Annotated

import typer

from wf_cli.context import config_path_from_context, load_cli_context
from wf_cli.formats import ListOutputFormat, emit_list_payload
from wf_cli.io import emit_json

app = typer.Typer(
    name="cap",
    help="Inspect and call workflow capabilities.",
    no_args_is_help=True,
)


@app.command("list")
def list_capabilities(
    ctx: typer.Context,
    query: Annotated[str | None, typer.Option("--query", help="Search capability names/descriptions.")] = None,
    source_id: Annotated[str | None, typer.Option("--source", help="Filter by source id.")] = None,
    cursor: Annotated[str | None, typer.Option("--cursor", help="Pagination cursor.")] = None,
    limit: Annotated[int, typer.Option("--limit", min=1, max=100, help="Maximum rows.")] = 50,
    output_format: Annotated[ListOutputFormat, typer.Option("--format", help="Output format.")] = ListOutputFormat.JSON,
) -> None:
    """List compact planner-visible workflow capabilities."""
    context = load_cli_context(config_path_from_context(ctx))
    payload = asyncio.run(
        context.handlers.list_capabilities(
            query=query,
            source_id=source_id,
            cursor=cursor,
            limit=limit,
        )
    )
    emit_list_payload(
        payload,
        collection_key="capabilities",
        output_format=output_format,
        id_field="name",
        summary_fields=("source_id", "kind", "description"),
    )


@app.command("inspect")
def inspect_capability(
    ctx: typer.Context,
    qualified_name: Annotated[str, typer.Argument(help="Workflow capability name.")],
) -> None:
    """Inspect one workflow capability contract."""
    context = load_cli_context(config_path_from_context(ctx))
    payload = asyncio.run(
        context.handlers.inspect_capability(qualified_name=qualified_name)
    )
    emit_json(payload)
```

- [ ] **Step 4: Run capability tests**

Run:

```bash
uv run pytest tests/wf_cli/test_discovery_lifecycle.py tests/wf_cli/test_app.py -q
```

Expected: pass.

## Task 3: Artifact And Deployment Store Commands

**Files:**

- Modify: `src/wf_cli/commands/artifacts.py`
- Modify: `src/wf_cli/commands/deployments.py`
- Test: `tests/wf_cli/test_discovery_lifecycle.py`
- Test: `tests/wf_cli/test_app.py`

- [ ] **Step 1: Add artifact/deployment CLI tests**

Append to `tests/wf_cli/test_discovery_lifecycle.py`:

```python
def _seed_echo_artifact(root: Path) -> Path:
    config_path = _write_cli_config(root)
    store = FileWorkflowArtifactStore(root / ".wf_mcp_store")
    store.save_artifact(echo_artifact())
    return config_path


def _seed_echo_deployment(root: Path) -> Path:
    config_path = _seed_echo_artifact(root)
    store = FileWorkflowArtifactStore(root / ".wf_mcp_store")
    store.save_deployment(
        WorkflowDeployment(
            id="echo.personal",
            artifact_id="echo",
            artifact_version=1,
            bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
        )
    )
    return config_path


def test_wf_artifact_list_and_inspect() -> None:
    root = local_temp_root() / "wf_cli_artifacts"
    root.mkdir(parents=True, exist_ok=True)
    config_path = _seed_echo_artifact(root)

    listed = runner.invoke(app, ["--config", str(config_path), "artifact", "list", "--format", "ids"])
    inspected = runner.invoke(app, ["--config", str(config_path), "artifact", "inspect", "echo", "1"])

    assert listed.exit_code == 0
    assert listed.output.strip() == "workflow.echo.v1"
    assert inspected.exit_code == 0
    payload = json.loads(inspected.output)
    assert payload["id"] == "echo"
    assert payload["version"] == 1


def test_wf_deploy_list_inspect_save_delete() -> None:
    root = local_temp_root() / "wf_cli_deploy_lifecycle"
    root.mkdir(parents=True, exist_ok=True)
    config_path = _seed_echo_deployment(root)

    listed = runner.invoke(app, ["--config", str(config_path), "deploy", "list", "--format", "ids"])
    inspected = runner.invoke(app, ["--config", str(config_path), "deploy", "inspect", "echo.personal"])
    saved = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "deploy",
            "save",
            "echo.copy",
            "--artifact",
            "echo",
            "--version",
            "1",
            "--binding",
            "demo=demo.personal",
        ],
    )
    deleted = runner.invoke(app, ["--config", str(config_path), "deploy", "delete", "echo.copy"])

    assert listed.exit_code == 0
    assert listed.output.strip() == "echo.personal"
    assert inspected.exit_code == 0
    assert json.loads(inspected.output)["id"] == "echo.personal"
    assert saved.exit_code == 0
    assert json.loads(saved.output)["deployment_id"] == "echo.copy"
    assert deleted.exit_code == 0
    assert json.loads(deleted.output)["deleted"] is True
```

Append to `tests/wf_cli/test_app.py`:

```python
def test_wf_artifact_list_help_exists() -> None:
    result = runner.invoke(app, ["artifact", "list", "--help"])

    assert result.exit_code == 0
    assert "--format" in result.output


def test_wf_deploy_save_help_exists() -> None:
    result = runner.invoke(app, ["deploy", "save", "--help"])

    assert result.exit_code == 0
    assert "--binding" in result.output
```

- [ ] **Step 2: Run artifact/deployment tests to verify failure**

Run:

```bash
uv run pytest tests/wf_cli/test_discovery_lifecycle.py tests/wf_cli/test_app.py -q
```

Expected: fail because artifact and deployment lifecycle commands do not exist.

- [ ] **Step 3: Implement artifact commands**

Replace `src/wf_cli/commands/artifacts.py` with:

```python
from __future__ import annotations

import asyncio
from typing import Annotated, Literal

import typer

from wf_cli.context import config_path_from_context, load_cli_context
from wf_cli.formats import ListOutputFormat, emit_list_payload
from wf_cli.io import emit_json

app = typer.Typer(
    name="artifact",
    help="List and inspect saved workflow artifacts.",
    no_args_is_help=True,
)


@app.command("list")
def list_artifacts(
    ctx: typer.Context,
    query: Annotated[str | None, typer.Option("--query", help="Search artifact summaries.")] = None,
    kind: Annotated[Literal["workflow", "wrapper"] | None, typer.Option("--kind", help="Filter artifact kind.")] = None,
    cursor: Annotated[str | None, typer.Option("--cursor", help="Pagination cursor.")] = None,
    limit: Annotated[int, typer.Option("--limit", min=1, max=100, help="Maximum rows.")] = 50,
    output_format: Annotated[ListOutputFormat, typer.Option("--format", help="Output format.")] = ListOutputFormat.JSON,
) -> None:
    """List compact saved artifact summaries."""
    context = load_cli_context(config_path_from_context(ctx))
    payload = asyncio.run(
        context.handlers.list_artifacts(
            query=query,
            kind=kind,
            cursor=cursor,
            limit=limit,
        )
    )
    emit_list_payload(
        payload,
        collection_key="nodes",
        output_format=output_format,
        id_field="name",
        summary_fields=("kind", "display_name", "description"),
    )


@app.command("inspect")
def inspect_artifact(
    ctx: typer.Context,
    artifact_id: Annotated[str, typer.Argument(help="Artifact id.")],
    version: Annotated[int, typer.Argument(min=1, help="Artifact version.")],
) -> None:
    """Inspect one saved artifact version."""
    context = load_cli_context(config_path_from_context(ctx))
    emit_json(
        asyncio.run(
            context.handlers.inspect_artifact(artifact_id=artifact_id, version=version)
        )
    )
```

- [ ] **Step 4: Implement deployment commands**

Extend `src/wf_cli/commands/deployments.py` without removing the existing `validate` command:

```python
from pathlib import Path

from wf_cli.formats import ListOutputFormat, emit_list_payload
from wf_cli.io import CliInputError, emit_json, parse_json_input
```

Add these commands above or below `validate_deployment`:

```python
@app.command("list")
def list_deployments(
    ctx: typer.Context,
    output_format: Annotated[ListOutputFormat, typer.Option("--format", help="Output format.")] = ListOutputFormat.JSON,
) -> None:
    """List saved workflow deployments."""
    context = load_cli_context(config_path_from_context(ctx))
    payload = asyncio.run(context.handlers.list_deployments())
    emit_list_payload(
        payload,
        collection_key="deployments",
        output_format=output_format,
        id_field="id",
        summary_fields=("artifact_id", "artifact_version", "drift_policy"),
    )


@app.command("inspect")
def inspect_deployment(
    ctx: typer.Context,
    deployment_id: Annotated[str, typer.Argument(help="Deployment id.")],
) -> None:
    """Inspect one saved deployment."""
    context = load_cli_context(config_path_from_context(ctx))
    emit_json(asyncio.run(context.handlers.inspect_deployment(deployment_id=deployment_id)))


@app.command("save")
def save_deployment(
    ctx: typer.Context,
    deployment_id: Annotated[str | None, typer.Argument(help="Deployment id.")] = None,
    artifact_id: Annotated[str | None, typer.Option("--artifact", help="Artifact id.")] = None,
    version: Annotated[int | None, typer.Option("--version", min=1, help="Artifact version.")] = None,
    binding: Annotated[list[str] | None, typer.Option("--binding", help="Logical=concrete source binding. Repeatable.")] = None,
    input_json: Annotated[str | None, typer.Option("--input", help="Full deployment JSON object.")] = None,
    input_file: Annotated[Path | None, typer.Option("--input-file", help="Path to full deployment JSON object.")] = None,
) -> None:
    """Save a workflow deployment from flags or a JSON object."""
    try:
        if input_json is not None or input_file is not None:
            payload = parse_json_input(input_json=input_json, input_file=input_file)
        else:
            payload = _deployment_payload_from_flags(
                deployment_id=deployment_id,
                artifact_id=artifact_id,
                version=version,
                bindings=binding or [],
            )
    except CliInputError as exc:
        raise typer.BadParameter(str(exc)) from exc
    context = load_cli_context(config_path_from_context(ctx))
    emit_json(asyncio.run(context.handlers.save_deployment(payload)))


@app.command("delete")
def delete_deployment(
    ctx: typer.Context,
    deployment_id: Annotated[str, typer.Argument(help="Deployment id.")],
) -> None:
    """Delete one saved deployment."""
    context = load_cli_context(config_path_from_context(ctx))
    emit_json(asyncio.run(context.handlers.delete_deployment(deployment_id=deployment_id)))


def _deployment_payload_from_flags(
    *,
    deployment_id: str | None,
    artifact_id: str | None,
    version: int | None,
    bindings: list[str],
) -> dict[str, object]:
    """Build deployment JSON from ergonomic flags without hiding the model shape."""
    if deployment_id is None or artifact_id is None or version is None:
        raise CliInputError("deployment_id, --artifact, and --version are required without --input")
    return {
        "deployment_id": deployment_id,
        "artifact_id": artifact_id,
        "artifact_version": version,
        "bindings": _parse_bindings(bindings),
    }


def _parse_bindings(bindings: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in bindings:
        logical, separator, concrete = item.partition("=")
        if separator != "=" or not logical or not concrete:
            raise CliInputError("--binding must use logical=concrete")
        parsed[logical] = concrete
    return parsed
```

- [ ] **Step 5: Run artifact/deployment tests**

Run:

```bash
uv run pytest tests/wf_cli/test_discovery_lifecycle.py tests/wf_cli/test_app.py -q
```

Expected: pass.

## Task 4: Draft Workspace Commands

**Files:**

- Modify: `src/wf_cli/commands/drafts.py`
- Test: `tests/wf_cli/test_discovery_lifecycle.py`
- Test: `tests/wf_cli/test_app.py`

- [ ] **Step 1: Add draft lifecycle CLI tests**

Append to `tests/wf_cli/test_discovery_lifecycle.py`:

```python
def test_wf_draft_create_patch_validate_save() -> None:
    root = local_temp_root() / "wf_cli_draft_lifecycle"
    root.mkdir(parents=True, exist_ok=True)
    config_path = _write_cli_config(root)

    with patch("wf_cli.commands.drafts.load_cli_context", _load_cli_context_with_specs):
        created = runner.invoke(
            app,
            [
                "--config",
                str(config_path),
                "draft",
                "create-from-capability",
                "echo_workspace",
                "demo.personal.echo_tool",
                "--name",
                "echo_workspace",
            ],
        )
        listed = runner.invoke(app, ["--config", str(config_path), "draft", "list", "--format", "ids"])
        inspected = runner.invoke(app, ["--config", str(config_path), "draft", "inspect", "echo_workspace", "--include-draft"])
        revision = json.loads(created.output)["revision"]
        patched = runner.invoke(
            app,
            [
                "--config",
                str(config_path),
                "draft",
                "patch",
                "echo_workspace",
                "--revision",
                str(revision),
                "--input",
                '[{"op":"replace","path":"/name","value":"echo_workspace_renamed"}]',
            ],
        )
        validated = runner.invoke(app, ["--config", str(config_path), "draft", "validate", "echo_workspace"])
        saved = runner.invoke(
            app,
            [
                "--config",
                str(config_path),
                "draft",
                "save",
                "echo_workspace",
                "--artifact",
                "echo_workspace",
                "--version",
                "1",
                "--title",
                "Echo Workspace",
                "--outcome",
                "completed",
                "--binding",
                "demo=demo.personal",
            ],
        )

    assert created.exit_code == 0
    assert json.loads(created.output)["workspace_id"] == "echo_workspace"
    assert listed.exit_code == 0
    assert listed.output.strip() == "echo_workspace"
    assert inspected.exit_code == 0
    assert "draft" in json.loads(inspected.output)
    assert patched.exit_code == 0
    assert json.loads(patched.output)["revision"] == revision + 1
    assert validated.exit_code == 0
    assert json.loads(validated.output)["status"] == "valid"
    assert saved.exit_code == 0
    assert json.loads(saved.output)["saved"] is True
```

Append to `tests/wf_cli/test_app.py`:

```python
def test_wf_draft_create_from_capability_help_exists() -> None:
    result = runner.invoke(app, ["draft", "create-from-capability", "--help"])

    assert result.exit_code == 0
    assert "--title" in result.output
```

- [ ] **Step 2: Run draft tests to verify failure**

Run:

```bash
uv run pytest tests/wf_cli/test_discovery_lifecycle.py tests/wf_cli/test_app.py -q
```

Expected: fail because draft lifecycle commands do not exist.

- [ ] **Step 3: Implement draft commands**

Replace `src/wf_cli/commands/drafts.py` with:

```python
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated, Literal

import typer

from wf_cli.context import config_path_from_context, load_cli_context
from wf_cli.formats import ListOutputFormat, emit_list_payload
from wf_cli.io import CliInputError, emit_json, parse_json_value

app = typer.Typer(
    name="draft",
    help="Create, inspect, patch, validate, and save draft workflows.",
    no_args_is_help=True,
)


@app.command("list")
def list_drafts(
    ctx: typer.Context,
    output_format: Annotated[ListOutputFormat, typer.Option("--format", help="Output format.")] = ListOutputFormat.JSON,
) -> None:
    """List stored draft workspaces."""
    context = load_cli_context(config_path_from_context(ctx))
    payload = asyncio.run(context.handlers.list_draft_workspaces())
    emit_list_payload(
        payload,
        collection_key="workspaces",
        output_format=output_format,
        id_field="workspace_id",
        summary_fields=("title", "revision", "status"),
    )


@app.command("inspect")
def inspect_draft(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    include_draft: Annotated[bool, typer.Option("--include-draft", help="Include full draft JSON.")] = False,
) -> None:
    """Inspect one draft workspace."""
    context = load_cli_context(config_path_from_context(ctx))
    emit_json(
        asyncio.run(
            context.handlers.get_draft_workspace(
                workspace_id=workspace_id,
                include_draft=include_draft,
            )
        )
    )


@app.command("create-from-capability")
def create_from_capability(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    capability_name: Annotated[str, typer.Argument(help="Workflow capability name.")],
    name: Annotated[str | None, typer.Option("--name", help="Draft workflow name.")] = None,
    title: Annotated[str | None, typer.Option("--title", help="Workspace title.")] = None,
) -> None:
    """Bootstrap a draft workspace from inspect_capability wrapper hints."""
    context = load_cli_context(config_path_from_context(ctx))
    emit_json(
        asyncio.run(
            context.handlers.create_draft_workspace_from_capability(
                workspace_id=workspace_id,
                capability_name=capability_name,
                name=name,
                title=title,
            )
        )
    )


@app.command("patch")
def patch_draft(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    revision: Annotated[int, typer.Option("--revision", min=1, help="Expected workspace revision.")],
    input_json: Annotated[str | None, typer.Option("--input", help="JSON Patch array.")] = None,
    input_file: Annotated[Path | None, typer.Option("--input-file", help="Path to JSON Patch array.")] = None,
) -> None:
    """Apply an RFC 6902 JSON Patch to a draft workspace."""
    try:
        patch = parse_json_value(input_json=input_json, input_file=input_file)
    except CliInputError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if not isinstance(patch, list):
        raise typer.BadParameter("draft patch input must be a JSON array")
    context = load_cli_context(config_path_from_context(ctx))
    emit_json(
        asyncio.run(
            context.handlers.patch_draft_workspace(
                workspace_id=workspace_id,
                revision=revision,
                patch=patch,
            )
        )
    )


@app.command("validate")
def validate_draft(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
) -> None:
    """Validate one stored draft workspace."""
    context = load_cli_context(config_path_from_context(ctx))
    emit_json(asyncio.run(context.handlers.validate_draft_workspace(workspace_id=workspace_id)))


@app.command("save")
def save_draft(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    artifact_id: Annotated[str, typer.Option("--artifact", help="Artifact id.")],
    version: Annotated[int, typer.Option("--version", min=1, help="Artifact version.")],
    title: Annotated[str, typer.Option("--title", help="Artifact title.")],
    outcome: Annotated[list[str] | None, typer.Option("--outcome", help="Artifact outcome. Repeatable.")] = None,
    kind: Annotated[Literal["workflow", "wrapper"], typer.Option("--kind", help="Artifact kind.")] = "workflow",
    description: Annotated[str | None, typer.Option("--description", help="Artifact description.")] = None,
    binding: Annotated[list[str] | None, typer.Option("--binding", help="Logical=concrete source binding. Repeatable.")] = None,
) -> None:
    """Save a validated draft workspace as a workflow or wrapper artifact."""
    source_bindings = _parse_bindings(binding or [])
    context = load_cli_context(config_path_from_context(ctx))
    if kind == "wrapper":
        payload = asyncio.run(
            context.handlers.create_wrapper_from_workspace(
                workspace_id=workspace_id,
                artifact_id=artifact_id,
                version=version,
                title=title,
                outcomes=tuple(outcome or ["ok"]),
                description=description,
                source_bindings=source_bindings or None,
            )
        )
    else:
        payload = asyncio.run(
            context.handlers.create_artifact_from_workspace(
                workspace_id=workspace_id,
                artifact_id=artifact_id,
                version=version,
                title=title,
                outcomes=tuple(outcome or ["ok"]),
                kind="workflow",
                description=description,
                source_bindings=source_bindings or None,
            )
        )
    emit_json(payload)


def _parse_bindings(bindings: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in bindings:
        logical, separator, concrete = item.partition("=")
        if separator != "=" or not logical or not concrete:
            raise typer.BadParameter("--binding must use logical=concrete")
        parsed[logical] = concrete
    return parsed
```

- [ ] **Step 4: Run draft tests**

Run:

```bash
uv run pytest tests/wf_cli/test_discovery_lifecycle.py tests/wf_cli/test_app.py -q
```

Expected: pass.

## Task 5: Focused Verification

**Files:**

- No new files unless lint/format requires cleanup.

- [ ] **Step 1: Run focused CLI tests**

Run:

```bash
uv run pytest tests/wf_cli -q
```

Expected: all CLI tests pass.

- [ ] **Step 2: Run focused lint**

Run:

```bash
uv run ruff check src/wf_cli tests/wf_cli
```

Expected: no lint errors.

- [ ] **Step 3: Run focused format check**

Run:

```bash
uv run ruff format --check src/wf_cli tests/wf_cli
```

Expected: no formatting changes required. If this fails, run:

```bash
uv run ruff format src/wf_cli tests/wf_cli
```

Then rerun the format check.

- [ ] **Step 4: Run type check**

Run:

```bash
uv run basedpyright --level error
```

Expected: `0 errors`. If basedpyright exits nonzero only because workspace file enumeration exceeds 10 seconds while still reporting `0 errors`, report that exact condition.

## Self-Review Checklist

- [ ] List commands support only `json`, `ids`, and `compact`.
- [ ] Detail and mutation commands stay JSON-only.
- [ ] No `table` format was added.
- [ ] Draft patch accepts a JSON Patch array, not only a JSON object.
- [ ] `deploy save` accepts ergonomic flags and full JSON input.
- [ ] `draft save --kind wrapper` calls `create_wrapper_from_workspace`.
- [ ] No workflow-surface handler behavior was reimplemented in CLI code.
- [ ] Tests assert individual fields, not whole dict equality.
