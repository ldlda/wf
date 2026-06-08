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


@dataclass(frozen=True)
class _Context:
    handlers: _ArtifactHandlers


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
