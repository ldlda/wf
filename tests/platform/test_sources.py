from __future__ import annotations

from wf_platform import (
    CapabilityBuckets,
    CapabilitySource,
    DocumentationPrompt,
    DocumentationResource,
    SourceInventory,
    SourcePermissions,
    SourcePolicy,
    SourceStatus,
    SourceVisibility,
    build_documentation_source,
)


def test_capability_source_projects_typed_status() -> None:
    source = CapabilitySource(
        id="wf.std",
        kind="system",
        capabilities=CapabilityBuckets(
            tools={
                "wf.std.inspect": object(),
                "wf.std.zeta": object(),
                "wf.std.alpha": object(),
                "wf.std.beta": object(),
            },
            resources={"wf.std.manual": object()},
        ),
        visibility=SourceVisibility(planner=True, client=True),
        permissions=SourcePermissions(safe_for_workflow=True),
        description="Workflow standard library.",
    )

    status = source.as_status()

    assert isinstance(status, SourceStatus)
    assert status.id == "wf.std"
    assert status.visibility.planner is True
    assert status.permissions.safe_for_workflow is True
    assert status.tool_count == 4
    assert status.preview.tools == (
        "wf.std.alpha",
        "wf.std.beta",
        "wf.std.inspect",
    )
    assert status.has_more.tools is True
    assert status.resource_count == 1
    assert status.preview.resources == ("wf.std.manual",)
    assert status.has_more.resources is False


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
        ],
        prompts=[
            DocumentationPrompt(
                name="wf.docs.operator_guide",
                title="Operator Guide",
                description="Guide a human operator to the right manuals.",
                text="Read wf://docs/operator-manual first.",
            )
        ],
    )

    resource = source.capabilities.resources["wf.docs.operator_manual"]

    assert source.id == "wf.docs"
    assert source.visibility.client is True
    assert resource.uri == "wf://docs/operator-manual"
    assert resource.text == "# Operator Manual"
    assert source.capabilities.prompts["wf.docs.operator_guide"].text == (
        "Read wf://docs/operator-manual first."
    )


def test_capability_source_exposes_policy_snapshot() -> None:
    source = CapabilitySource(
        id="wf.std",
        kind="system",
        policy=SourcePolicy(platform=True, binding_required=False),
    )

    status = source.as_status()

    assert status.policy.platform is True
    assert status.policy.binding_required is False
    assert status.model_dump(mode="json")["policy"] == {
        "platform": True,
        "binding_required": False,
    }
