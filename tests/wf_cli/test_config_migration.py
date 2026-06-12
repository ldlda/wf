from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from wf_cli.app import app


def test_wf_config_migrate_mcp_prints_neutral_config(tmp_path: Path) -> None:
    legacy_path = tmp_path / "wf_mcp.config.json"
    legacy_path.write_text(
        """
{
  "store_root": ".wf_mcp_store",
  "connections": [
    {
      "id": "everything.default",
      "server": "everything",
      "account": "default",
      "metadata": {
        "transport": "stdio",
        "command": "uvx",
        "args": ["mcp-server-everything"]
      }
    }
  ]
}
""",
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["config", "migrate-mcp", str(legacy_path)])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["server"]["store"] == {
        "kind": "filesystem",
        "root": ".wf_mcp_store",
    }
    source = payload["server"]["sources"][0]
    assert source["kind"] == "mcp"
    assert source["id"] == "everything.default"
    assert source["transport"]["kind"] == "stdio"
    assert source["transport"]["command"] == "uvx"


def test_wf_config_migrate_mcp_writes_output_file(tmp_path: Path) -> None:
    legacy_path = tmp_path / "wf_mcp.config.json"
    output_path = tmp_path / "wf.json"
    legacy_path.write_text(
        """
{
  "store_root": "store",
  "connections": [
    {
      "id": "context7.default",
      "server": "context7",
      "account": "default",
      "metadata": {
        "transport": "streamable_http",
        "url": "http://127.0.0.1:3000/mcp"
      }
    }
  ]
}
""",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        ["config", "migrate-mcp", str(legacy_path), "--output", str(output_path)],
    )

    assert result.exit_code == 0, result.output
    status = json.loads(result.output)
    assert status["status"] == "written"
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["server"]["sources"][0]["transport"]["kind"] == "http"


def test_wf_config_validate_loads_python_source(tmp_path: Path) -> None:
    source_root = tmp_path / "sources"
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
def echo(input: EchoInput) -> EchoOutput:
    return EchoOutput(text=input.text)


registry = [echo]
""",
        encoding="utf-8",
    )
    config_path = tmp_path / "wf.config.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "server": {
                    "store": {"kind": "filesystem", "root": "store"},
                    "sources": [
                        {
                            "kind": "python",
                            "id": "local.ops",
                            "path": "sources",
                            "module": "ops",
                            "registry": "registry",
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["config", "validate", str(config_path)])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["valid"] is True
    assert payload["sources"] == [
        {
            "id": "local.ops",
            "kind": "python",
            "status": "ok",
            "capability_count": 1,
        }
    ]


def test_wf_config_validate_reports_python_source_import_failure(tmp_path: Path) -> None:
    config_path = tmp_path / "wf.config.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "server": {
                    "store": {"kind": "filesystem", "root": "store"},
                    "sources": [
                        {
                            "kind": "python",
                            "id": "local.ops",
                            "path": ".",
                            "module": "missing_ops",
                            "registry": "registry",
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["config", "validate", str(config_path)])

    assert result.exit_code != 0
    assert "invalid workflow config" in result.output
    assert "local.ops" in result.output
    assert "missing_ops" in result.output
