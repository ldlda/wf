from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .service import WfMcpService

_WORKFLOW_AUTHORING_GUIDE = """\
Build workflows from current capabilities instead of assuming a stale catalog.

Use `get_planner_catalog` when you need the current workflow-capability view.
Use `list_sources` when you need to understand source ownership, visibility,
and capability kinds.
Use source-projected workflow capabilities or directly exposed proxy tools to
test the smallest reusable piece before wrapping it into a workflow.

Prefer namespaced capabilities, inspect before you rely on them, and test the
smallest reusable piece before saving a larger workflow artifact.
"""


def register_broker_prompts(server: FastMCP, service: WfMcpService) -> None:
    """Register broker prompt handlers on a FastMCP server."""

    @server.prompt(
        name="workflow_authoring_guide",
        description="Explain how to inspect capabilities and test tools before authoring.",
    )
    def workflow_authoring_guide() -> list[dict[str, str]]:
        _ = service
        return [
            {
                "role": "user",
                "content": _WORKFLOW_AUTHORING_GUIDE,
            }
        ]
