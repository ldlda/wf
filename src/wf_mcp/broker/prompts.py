from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from .service import WfMcpService


def register_broker_prompts(server: FastMCP, service: WfMcpService) -> None:
    """Register broker prompt handlers on a FastMCP server."""

    @server.prompt(
        name="plan_with_catalog",
        description="Provide the broker catalog as planning context.",
    )
    def plan_with_catalog() -> list[dict[str, str]]:
        payload = json.dumps(service.get_catalog().as_payload(), indent=2)
        return [
            {
                "role": "user",
                "content": (
                    "Plan a workflow using this broker catalog. "
                    "Prefer existing namespaced capabilities.\n\n"
                    f"{payload}"
                ),
            }
        ]
