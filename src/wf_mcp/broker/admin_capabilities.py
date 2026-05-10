from __future__ import annotations

from dataclasses import dataclass

from .service.capability_sources import (
    CapabilityBuckets,
    CapabilitySource,
    SourcePermissions,
    SourceVisibility,
)


ADMIN_SOURCE_ID = "wf.admin"


@dataclass(frozen=True, slots=True)
class AdminTool:
    name: str
    description: str
    handler_name: str
    mutates_config: bool = False
    mutates_auth: bool = False


def admin_source() -> CapabilitySource:
    """Return metadata for privileged broker administration tools."""
    tools = {
        tool.name: tool
        for tool in (
            AdminTool(
                name="wf.admin.list_sources",
                description="List broker capability sources.",
                handler_name="list_sources",
            ),
            AdminTool(
                name="wf.admin.disable_source",
                description="Disable a broker capability source.",
                handler_name="disable_source",
                mutates_config=True,
            ),
            AdminTool(
                name="wf.admin.enable_source",
                description="Enable a broker capability source.",
                handler_name="enable_source",
                mutates_config=True,
            ),
        )
    }
    return CapabilitySource(
        id=ADMIN_SOURCE_ID,
        kind="system",
        capabilities=CapabilityBuckets(tools=tools),
        visibility=SourceVisibility(
            planner=False,
            mcp_client=False,
            admin_dashboard=True,
        ),
        permissions=SourcePermissions(
            safe_for_workflow=False,
            calls_upstream=False,
            mutates_config=True,
            mutates_auth=True,
        ),
        description="Privileged broker administration capabilities.",
    )
