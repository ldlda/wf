from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from wf_mcp.models import BrokerConfig, ConnectionConfig

from ..test_support import fixture_server_path, local_temp_root


def structured(result: Any) -> dict[str, Any]:
    content = result.structured_content
    assert isinstance(content, dict)
    return content


def proxy_config(tmp_path: Path = local_temp_root()) -> BrokerConfig:
    return BrokerConfig(
        store_root=tmp_path / "proxy_store",
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
