from __future__ import annotations

from wf_platform import (
    CapabilityBuckets,
    CapabilitySource,
    DocumentationResource,
    SourceInventory,
    SourcePermissions,
    SourceStatus,
    SourceVisibility,
    build_documentation_source,
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


def test_documentation_source_owns_provider_neutral_resources() -> None:
    source = build_documentation_source(
        [
            DocumentationResource(
                name="wf.docs.operator_manual",
                uri="wf://docs/operator-manual",
                title="Operator Manual",
                description="How to operate the platform.",
                mime_type="text/markdown",
                text="# Operator Manual",
            )
        ]
    )

    resource = source.capabilities.resources["wf.docs.operator_manual"]

    assert source.id == "wf.docs"
    assert source.visibility.mcp_client is True
    assert resource.uri == "wf://docs/operator-manual"
    assert resource.text == "# Operator Manual"
