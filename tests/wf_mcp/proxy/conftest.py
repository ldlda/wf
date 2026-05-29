from __future__ import annotations

import sys
from typing import Any

from wf_mcp.models import BrokerConfig, ConnectionConfig
from wf_mcp.proxy import create_proxy_client

from ..test_support import fixture_server_path, local_temp_root


def structured(result: Any) -> dict[str, Any]:
    content = result.structured_content
    assert isinstance(content, dict)
    return content


def proxy_config() -> BrokerConfig:
    return BrokerConfig(
        store_root=local_temp_root() / "proxy_store",
        connections=[
            ConnectionConfig(
                id="fixture.personal",
                server="fixture",
                account="personal",
                metadata={
                    "transport": "stdio",
                    "command": sys.executable,
                    "args": [fixture_server_path()],
                },
            )
        ],
    )
