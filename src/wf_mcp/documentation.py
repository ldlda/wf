from __future__ import annotations

from pathlib import Path

from wf_platform import CapabilitySource, DocumentationResource, build_documentation_source


def build_local_documentation_source(repo_root: Path) -> CapabilitySource:
    """Load project manuals into a provider-neutral local documentation source."""
    docs_dir = repo_root / "docs"
    return build_documentation_source(
        [
            _markdown_resource(
                path=docs_dir / "wf_mcp_operator_manual.md",
                name="wf.docs.operator_manual",
                uri="wf://docs/operator-manual",
                title="wf_mcp Operator Manual",
                description="Short mental model and tool-family map for wf_mcp.",
            ),
            _markdown_resource(
                path=docs_dir / "wf_mcp_end_to_end_runbook.md",
                name="wf.docs.end_to_end_runbook",
                uri="wf://docs/end-to-end-runbook",
                title="wf_mcp End-To-End Runbook",
                description="Connection-to-deployment workflow runbook.",
            ),
            _markdown_resource(
                path=docs_dir / "wf_mcp_troubleshooting.md",
                name="wf.docs.troubleshooting",
                uri="wf://docs/troubleshooting",
                title="wf_mcp Troubleshooting",
                description="Failure-oriented guide for discovery and deployment issues.",
            ),
        ]
    )


def _markdown_resource(
    *,
    path: Path,
    name: str,
    uri: str,
    title: str,
    description: str,
) -> DocumentationResource:
    """Load one Markdown manual into the transport-neutral docs model."""
    return DocumentationResource(
        name=name,
        uri=uri,
        title=title,
        description=description,
        mime_type="text/markdown",
        text=path.read_text(encoding="utf-8"),
    )
