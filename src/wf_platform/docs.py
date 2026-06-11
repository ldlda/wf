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


@dataclass(frozen=True, slots=True)
class DocumentationPrompt:
    """Provider-neutral prompt that guides a client toward documentation."""

    name: str
    title: str
    description: str
    text: str


def build_documentation_source(
    resources: list[DocumentationResource],
    *,
    prompts: list[DocumentationPrompt] | None = None,
) -> CapabilitySource:
    """Build the local documentation source without depending on MCP transport."""
    return CapabilitySource(
        id="wf.docs",
        kind="system",
        capabilities=CapabilityBuckets(
            resources={resource.name: resource for resource in resources},
            prompts={prompt.name: prompt for prompt in prompts or []},
        ),
        visibility=SourceVisibility(client=True),
        description="Local operator and workflow documentation.",
    )
