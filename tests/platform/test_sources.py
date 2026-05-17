from __future__ import annotations

from wf_platform import (
    CapabilityBuckets,
    CapabilitySource,
    SourceInventory,
    SourcePermissions,
    SourceStatus,
    SourceVisibility,
)


def test_capability_source_projects_typed_status() -> None:
    source = CapabilitySource(
        id="wf.std",
        kind="system",
        capabilities=CapabilityBuckets(
            tools={"wf.std.inspect": object()},
            resources={"wf.std.manual": object()},
        ),
        visibility=SourceVisibility(planner=True, mcp_client=True),
        permissions=SourcePermissions(safe_for_workflow=True),
        description="Workflow standard library.",
    )

    status = source.as_status()

    assert isinstance(status, SourceStatus)
    assert status.id == "wf.std"
    assert status.visibility.planner is True
    assert status.permissions.safe_for_workflow is True
    assert status.tool_count == 1
    assert status.resource_count == 1


def test_capability_source_projects_typed_inventory() -> None:
    source = CapabilitySource(
        id="wf.std",
        kind="system",
        capabilities=CapabilityBuckets(
            tools={"wf.std.inspect": object()},
            resources={"wf.std.manual": object()},
        ),
    )

    inventory = source.as_inventory()

    assert isinstance(inventory, SourceInventory)
    assert inventory.capabilities.tools == ("wf.std.inspect",)
    assert inventory.capabilities.resources == ("wf.std.manual",)
    assert inventory.model_dump(mode="json")["capabilities"]["tools"] == [
        "wf.std.inspect"
    ]
