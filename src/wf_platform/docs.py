from __future__ import annotations

from dataclasses import dataclass

from .sources import CapabilityBuckets, CapabilitySource, SourceVisibility


@dataclass(frozen=True, slots=True)
class DocumentationResource:
    """Provider-neutral text resource intended for humans or authoring clients."""

    name: str
    uri: str
    title: str
    description: str
    mime_type: str
    text: str


def build_documentation_source(
    resources: list[DocumentationResource],
) -> CapabilitySource:
    """Build the local documentation source without depending on MCP transport."""
    return CapabilitySource(
        id="wf.docs",
        kind="system",
        capabilities=CapabilityBuckets(
            resources={resource.name: resource for resource in resources}
        ),
        visibility=SourceVisibility(mcp_client=True),
        description="Local operator and workflow documentation.",
    )
