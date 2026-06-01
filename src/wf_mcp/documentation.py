from __future__ import annotations

from pathlib import Path

from wf_platform import (
    CapabilitySource,
    DocumentationPrompt,
    DocumentationResource,
    build_documentation_source,
)


def build_local_documentation_source(repo_root: Path) -> CapabilitySource:
    """Load project manuals into a provider-neutral local documentation source."""
    docs_dir = repo_root / "docs"
    skills_dir = repo_root / "skills"
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
            _markdown_resource(
                path=docs_dir / "workflow_capabilities.md",
                name="wf.docs.workflow_capabilities",
                uri="wf://docs/workflow-capabilities",
                title="Workflow Capabilities",
                description=(
                    "Raw capabilities, workflow capabilities, wrappers, and "
                    "source ownership."
                ),
            ),
            _markdown_resource(
                path=docs_dir / "workflow_drafts.md",
                name="wf.docs.workflow_drafts",
                uri="wf://docs/workflow-drafts",
                title="Workflow Drafts",
                description="Draft and workspace authoring model for workflows.",
            ),
            _markdown_resource(
                path=skills_dir / "wf-workflow" / "SKILL.md",
                name="wf.skills.wf_workflow.skill",
                uri="wf://skills/wf-workflow/SKILL.md",
                title="wf-workflow Skill",
                description="Agent-facing workflow lifecycle skill entrypoint.",
            ),
            _markdown_resource(
                path=skills_dir
                / "wf-workflow"
                / "references"
                / "workflow-lifecycle.md",
                name="wf.skills.wf_workflow.workflow_lifecycle",
                uri="wf://skills/wf-workflow/references/workflow-lifecycle.md",
                title="wf-workflow Workflow Lifecycle Reference",
                description="Agent-facing workflow lifecycle and tool order.",
            ),
            _markdown_resource(
                path=skills_dir
                / "wf-workflow"
                / "references"
                / "capabilities-and-wrappers.md",
                name="wf.skills.wf_workflow.capabilities_and_wrappers",
                uri=("wf://skills/wf-workflow/references/capabilities-and-wrappers.md"),
                title="wf-workflow Capabilities And Wrappers Reference",
                description=(
                    "Agent-facing raw capability, workflow capability, and "
                    "wrapper guidance."
                ),
            ),
            _markdown_resource(
                path=skills_dir / "wf-workflow" / "references" / "draft-workspaces.md",
                name="wf.skills.wf_workflow.draft_workspaces",
                uri="wf://skills/wf-workflow/references/draft-workspaces.md",
                title="wf-workflow Draft Workspaces Reference",
                description="Agent-facing draft workspace authoring guidance.",
            ),
            _markdown_resource(
                path=skills_dir / "wf-workflow" / "references" / "troubleshooting.md",
                name="wf.skills.wf_workflow.troubleshooting",
                uri="wf://skills/wf-workflow/references/troubleshooting.md",
                title="wf-workflow Troubleshooting Reference",
                description="Agent-facing workflow troubleshooting ladder.",
            ),
        ],
        prompts=[
            DocumentationPrompt(
                name="wf.docs.operator_guide",
                title="wf_mcp Operator Guide",
                description="Choose the right wf_mcp manual for the task at hand.",
                text=(
                    "Use wf://docs/operator-manual for the platform mental model. "
                    "Use wf://docs/end-to-end-runbook for the normal connection-to-run "
                    "flow. Use wf://docs/workflow-capabilities for wrappers and "
                    "workflow-ready node contracts. Use wf://docs/workflow-drafts "
                    "for draft workspace authoring. "
                    "Use wf://docs/troubleshooting when a source, capability, "
                    "or deployment is missing or unrunnable."
                ),
            ),
            DocumentationPrompt(
                name="wf.docs.workflow_authoring_guide",
                title="Workflow Authoring Guide",
                description="Guide an authoring client through safe capability discovery.",
                text=(
                    "Start with wf.admin.list_sources, then use "
                    "wf.workflow.list_capabilities and "
                    "wf.workflow.inspect_capability. Test a small reusable piece with "
                    "wf.workflow.call_capability before saving a larger artifact. "
                    "Read wf://docs/workflow-capabilities for the wrapper model, "
                    "then wf://docs/workflow-drafts for the workspace tools."
                ),
            ),
            DocumentationPrompt(
                name="wf.docs.troubleshooting_guide",
                title="wf_mcp Troubleshooting Guide",
                description="Point a client to the failure-oriented manual.",
                text=(
                    "When a source, capability, or deployment is missing, inspect the "
                    "smallest layer first and read wf://docs/troubleshooting for the "
                    "diagnostic ladder."
                ),
            ),
        ],
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
