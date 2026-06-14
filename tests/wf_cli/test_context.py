from __future__ import annotations

import json
from pathlib import Path

import click
import pytest
import typer

from wf_api import WorkflowApi
from wf_cli.context import (
    CliTyperState,
    config_path_from_context,
    force_local_from_context,
    load_cli_context,
    rpc_timeout_from_context,
    rpc_url_from_context,
)
from wf_server import build_local_static_workflow_server


def _typer_context(obj: object | None) -> typer.Context:
    ctx = typer.Context(click.Command("wf"))
    ctx.obj = obj
    return ctx


def _write_python_source_config(root: Path, *, target: dict[str, object]) -> Path:
    source_root = root / "source"
    source_root.mkdir()
    (source_root / "ops.py").write_text(
        """
from pydantic import BaseModel

from wf_authoring import node


class EchoInput(BaseModel):
    text: str


class EchoOutput(BaseModel):
    text: str


@node(name="echo")
def echo(payload: EchoInput) -> EchoOutput:
    return EchoOutput(text=payload.text)


registry = [echo]
""".lstrip(),
        encoding="utf-8",
    )
    config_path = root / "wf.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "client": {"target": target},
                "server": {
                    "store": {"kind": "filesystem", "root": ".wf_store"},
                    "sources": [
                        {
                            "kind": "python",
                            "id": "local.ops",
                            "path": "source",
                            "module": "ops",
                            "registry": "registry",
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    return config_path


def test_cli_typer_state_reads_typed_context_object() -> None:
    ctx = _typer_context(
        CliTyperState(
            config_path="remote.json",
            force_local=True,
            rpc_url="http://127.0.0.1:8000/rpc",
            rpc_timeout_seconds=2.5,
        )
    )

    assert config_path_from_context(ctx) == "remote.json"
    assert force_local_from_context(ctx) is True
    assert rpc_url_from_context(ctx) == "http://127.0.0.1:8000/rpc"
    assert rpc_timeout_from_context(ctx) == 2.5


def test_cli_typer_state_accepts_legacy_dict_context_object() -> None:
    ctx = _typer_context(
        {
            "config_path": "legacy.json",
            "force_local": True,
            "rpc_url": "http://localhost:9000/rpc",
            "rpc_timeout_seconds": 3,
        }
    )

    assert config_path_from_context(ctx) == "legacy.json"
    assert force_local_from_context(ctx) is True
    assert rpc_url_from_context(ctx) == "http://localhost:9000/rpc"
    assert rpc_timeout_from_context(ctx) == 3.0


def test_cli_typer_state_defaults_for_missing_context_object() -> None:
    ctx = _typer_context(None)

    assert config_path_from_context(ctx) == "wf_mcp.config.json"
    assert force_local_from_context(ctx) is False
    assert rpc_url_from_context(ctx) is None
    assert rpc_timeout_from_context(ctx) is None


def test_load_cli_context_builds_service_and_handlers(tmp_path: Path) -> None:
    root = tmp_path / "wf_cli_context"
    root.mkdir()
    config_path = root / "wf_mcp.config.json"
    config_path.write_text(
        json.dumps(
            {
                "store_root": ".wf_mcp_store",
                "connections": [
                    {
                        "id": "demo.personal",
                        "server": "demo",
                        "account": "personal",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    context = load_cli_context(config_path)
    service = context.service
    assert service is not None
    assert isinstance(context.handlers, WorkflowApi)

    assert context.config_path == config_path
    assert service.connections.list_all()[0].id == "demo.personal"
    assert context.handlers.context.artifact_store is service.artifact_store
    assert (
        context.handlers.context.draft_workspace_store is service.draft_workspace_store
    )
    assert context.handlers.context.run_store is service.run_store


def test_load_cli_context_local_uses_workflow_store_override(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path = tmp_path / "wf.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "client": {"target": {"kind": "local"}},
                "server": {
                    "store": {"kind": "filesystem", "root": ".default"},
                    "stores": {
                        "workflow": {
                            "kind": "filesystem",
                            "root": ".workflow",
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def fake_build_local_static_workflow_server(root):
        captured["store_root"] = root
        return build_local_static_workflow_server(tmp_path / "actual")

    monkeypatch.setattr(
        "wf_cli.context.build_local_static_workflow_server",
        fake_build_local_static_workflow_server,
    )

    context = load_cli_context(config_path)

    assert context.service is None
    assert captured["store_root"] == (tmp_path / ".workflow").resolve()


@pytest.mark.asyncio
async def test_load_cli_context_local_composes_configured_python_sources(
    tmp_path: Path,
) -> None:
    config_path = _write_python_source_config(
        tmp_path,
        target={
            "kind": "rpc_http",
            "url": "http://127.0.0.1:8765/rpc",
        },
    )

    context = load_cli_context(config_path, force_local=True)

    listed = await context.handlers.list_capabilities(
        source_id="local.ops",
        limit=100,
    )
    assert {
        capability["name"] for capability in listed["capabilities"]
    } == {"local.ops.echo"}
