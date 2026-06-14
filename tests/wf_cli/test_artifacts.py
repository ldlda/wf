from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from typer.testing import CliRunner

from wf_cli.app import app


class _ArtifactHandlers:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    async def inspect_artifact(
        self,
        *,
        artifact_id: str,
        version: int,
    ) -> dict[str, Any]:
        self.calls.append((artifact_id, version))
        return {"id": artifact_id, "version": version}

    async def delete_artifact(
        self,
        *,
        artifact_id: str,
        version: int,
    ) -> dict[str, Any]:
        self.calls.append((artifact_id, version))
        return {
            "artifact_id": artifact_id,
            "version": version,
            "deleted": True,
            "blocked_by_deployments": [],
        }

    async def create_artifact_from_plan(
        self,
        *,
        artifact_id: str,
        version: int,
        title: str,
        plan: dict[str, Any],
        outcomes: tuple[str, ...],
        kind: str = "workflow",
        description: str | None = None,
        required_capabilities: dict[str, dict[str, Any]] | None = None,
        source_bindings: dict[str, str] | None = None,
        created_from_catalog_version: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append((artifact_id, version))
        return {
            "artifact_id": artifact_id,
            "version": version,
            "title": title,
            "plan_name": plan["name"],
            "outcomes": list(outcomes),
            "kind": kind,
            "source_bindings": source_bindings,
        }


class _BlockedArtifactHandlers:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    async def delete_artifact(
        self,
        *,
        artifact_id: str,
        version: int,
    ) -> dict[str, Any]:
        self.calls.append((artifact_id, version))
        return {
            "artifact_id": artifact_id,
            "version": version,
            "deleted": False,
            "blocked_by_deployments": ["echo.default"],
        }


@dataclass(frozen=True)
class _Context:
    handlers: _ArtifactHandlers


@dataclass(frozen=True)
class _BlockedContext:
    handlers: _BlockedArtifactHandlers


def test_artifact_inspect_accepts_version_option(monkeypatch) -> None:
    handlers = _ArtifactHandlers()
    monkeypatch.setattr(
        "wf_cli.commands.artifacts.load_cli_context",
        lambda _ctx: _Context(handlers=handlers),
    )

    result = CliRunner().invoke(
        app,
        ["artifact", "inspect", "demo_artifact", "--version", "2"],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {"id": "demo_artifact", "version": 2}
    assert handlers.calls == [("demo_artifact", 2)]


def test_artifact_inspect_keeps_positional_version(monkeypatch) -> None:
    handlers = _ArtifactHandlers()
    monkeypatch.setattr(
        "wf_cli.commands.artifacts.load_cli_context",
        lambda _ctx: _Context(handlers=handlers),
    )

    result = CliRunner().invoke(app, ["artifact", "inspect", "demo_artifact", "3"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {"id": "demo_artifact", "version": 3}
    assert handlers.calls == [("demo_artifact", 3)]


def test_artifact_delete_requires_confirm(monkeypatch) -> None:
    handlers = _ArtifactHandlers()
    monkeypatch.setattr(
        "wf_cli.commands.artifacts.load_cli_context",
        lambda _ctx: _Context(handlers=handlers),
    )

    result = CliRunner().invoke(app, ["artifact", "delete", "echo", "1"])

    assert result.exit_code != 0
    assert "confirm" in result.output.lower()


def test_artifact_delete_confirmed_succeeds(monkeypatch) -> None:
    handlers = _ArtifactHandlers()
    monkeypatch.setattr(
        "wf_cli.commands.artifacts.load_cli_context",
        lambda _ctx: _Context(handlers=handlers),
    )

    result = CliRunner().invoke(app, ["artifact", "delete", "echo", "1", "--confirm"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["artifact_id"] == "echo"
    assert payload["version"] == 1
    assert payload["deleted"] is True
    assert handlers.calls == [("echo", 1)]


def test_artifact_delete_blocked_returns_blocker_ids(monkeypatch) -> None:
    handlers = _BlockedArtifactHandlers()
    monkeypatch.setattr(
        "wf_cli.commands.artifacts.load_cli_context",
        lambda _ctx: _BlockedContext(handlers=handlers),
    )

    result = CliRunner().invoke(app, ["artifact", "delete", "echo", "1", "--confirm"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["deleted"] is False
    assert payload["blocked_by_deployments"] == ["echo.default"]


def test_artifact_create_from_plan_reads_yaml(monkeypatch, tmp_path) -> None:
    handlers = _ArtifactHandlers()
    monkeypatch.setattr(
        "wf_cli.commands.artifacts.load_cli_context",
        lambda _ctx: _Context(handlers=handlers),
    )
    plan_file = tmp_path / "plan.yaml"
    plan_file.write_text(
        """
name: yaml_plan
input_schema: {type: object, properties: {}}
state_schema: {type: object, properties: {}}
output_schema: {type: object, properties: {}}
outcomes: [ok]
start: __end__
nodes: []
edges: []
""",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "artifact",
            "create-from-plan",
            str(plan_file),
            "--artifact",
            "yaml_artifact",
            "--version",
            "1",
            "--title",
            "YAML Artifact",
            "--outcome",
            "ok",
            "--binding",
            "local.ops=local.ops",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["artifact_id"] == "yaml_artifact"
    assert payload["plan_name"] == "yaml_plan"
    assert payload["source_bindings"] == {"local.ops": "local.ops"}


def test_artifact_create_from_plan_rejects_non_object_yaml(monkeypatch, tmp_path) -> None:
    handlers = _ArtifactHandlers()
    monkeypatch.setattr(
        "wf_cli.commands.artifacts.load_cli_context",
        lambda _ctx: _Context(handlers=handlers),
    )
    plan_file = tmp_path / "plan.yaml"
    plan_file.write_text("- not\n- object\n", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "artifact",
            "create-from-plan",
            str(plan_file),
            "--artifact",
            "bad",
            "--version",
            "1",
            "--title",
            "Bad",
        ],
    )

    assert result.exit_code != 0
    assert "structured file must contain an object" in result.output.lower()
