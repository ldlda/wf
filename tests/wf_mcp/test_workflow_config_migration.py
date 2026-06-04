from __future__ import annotations

from pathlib import Path

from wf_config.models import McpSourceConfig
from wf_mcp.broker.config import migrate_broker_config_file


def test_migrate_broker_config_file_converts_stdio_connection(tmp_path: Path) -> None:
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
      "enabled": true,
      "source_config_ownership": "seed",
      "metadata": {
        "transport": "stdio",
        "command": "uvx",
        "args": ["mcp-server-everything"],
        "env": {"DEBUG": "1"},
        "profile": "dev",
        "auth_ref": "auth.everything.default",
        "description": "Everything test server"
      }
    }
  ]
}
""",
        encoding="utf-8",
    )

    config = migrate_broker_config_file(legacy_path)

    assert config.server.store.kind == "filesystem"
    assert config.server.store.root == Path(".wf_mcp_store")
    assert len(config.server.sources) == 1
    source = config.server.sources[0]
    assert isinstance(source, McpSourceConfig)
    assert source.kind == "mcp"
    assert source.id == "everything.default"
    assert source.provider == "everything"
    assert source.account == "default"
    assert source.enabled is True
    assert source.ownership == "seed"
    assert source.profile == "dev"
    assert source.auth_ref == "auth.everything.default"
    assert source.transport.kind == "stdio"
    assert source.transport.command == "uvx"
    assert source.transport.args == ("mcp-server-everything",)
    assert source.transport.env == {"DEBUG": "1"}
    assert source.metadata["description"] == "Everything test server"


def test_migrate_broker_config_file_converts_streamable_http_connection(
    tmp_path: Path,
) -> None:
    legacy_path = tmp_path / "wf_mcp.config.json"
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
        "transport": "streamable-http",
        "url": "http://127.0.0.1:3000/mcp",
        "headers": {"X-Test": "yes"},
        "description": "HTTP server"
      }
    }
  ]
}
""",
        encoding="utf-8",
    )

    config = migrate_broker_config_file(legacy_path)

    source = config.server.sources[0]
    assert isinstance(source, McpSourceConfig)
    assert source.kind == "mcp"
    assert source.transport.kind == "http"
    assert str(source.transport.url) == "http://127.0.0.1:3000/mcp"
    assert source.transport.headers == {"X-Test": "yes"}
    assert source.metadata["description"] == "HTTP server"
    assert source.metadata["legacy_transport"] == "streamable-http"


def test_migrate_broker_config_file_converts_sse_connection(tmp_path: Path) -> None:
    legacy_path = tmp_path / "wf_mcp.config.json"
    legacy_path.write_text(
        """
{
  "store_root": "store",
  "connections": [
    {
      "id": "legacy.default",
      "server": "legacy",
      "account": "default",
      "metadata": {
        "transport": "sse",
        "url": "http://127.0.0.1:3000/sse"
      }
    }
  ]
}
""",
        encoding="utf-8",
    )

    config = migrate_broker_config_file(legacy_path)

    source = config.server.sources[0]
    assert isinstance(source, McpSourceConfig)
    assert source.transport.kind == "http"
    assert str(source.transport.url) == "http://127.0.0.1:3000/sse"
    assert source.metadata["legacy_transport"] == "sse"
