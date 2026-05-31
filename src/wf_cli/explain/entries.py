from __future__ import annotations

from .models import ExplainCard


EXPLAIN_CARDS: tuple[ExplainCard, ...] = (
    ExplainCard(
        code="source_missing",
        summary="A required logical source is not available or not bound.",
        why_it_happens=[
            "The artifact requires a logical source that the deployment did not bind.",
            "The concrete source was removed, renamed, disabled, or never registered.",
            "A saved wrapper or workflow depends on a source that is absent in this config.",
        ],
        how_to_fix=[
            "Run `wf deploy inspect <deployment_id>` and check the bindings.",
            "Run `wf cap list` to confirm the concrete source is available.",
            "Save the deployment again with the missing logical source bound.",
            "Run `wf deploy validate <deployment_id> --live` after changing bindings.",
        ],
        related_docs=[
            "docs/superpowers/specs/2026-06-01-wf-cli-design.md",
            "docs/workflow_capabilities.md",
        ],
    ),
    ExplainCard(
        code="source_unreachable",
        summary="A concrete source exists in config but could not be reached.",
        why_it_happens=[
            "The upstream MCP server or local process failed during liveness checks.",
            "The source command, URL, authentication, or environment is invalid.",
            "The source is slow or hung and exceeded the bounded liveness timeout.",
        ],
        how_to_fix=[
            "Check the source command or URL in the active config.",
            "Start or restart the upstream server.",
            "Run validation without `--live` if you only need static deployment checks.",
            "Run `wf deploy validate <deployment_id> --live` again after fixing the source.",
        ],
        related_docs=[
            "docs/wf_mcp_operator_manual.md",
            "docs/wf_mcp_proxy_reality_and_roadmap.md",
        ],
    ),
    ExplainCard(
        code="binding_missing",
        summary="A deployment is missing a required logical-to-concrete source binding.",
        why_it_happens=[
            "The artifact was saved with required capabilities under a logical source.",
            "The deployment was saved without a binding for that logical source.",
            "A binding field was misspelled or placed under the wrong payload key.",
        ],
        how_to_fix=[
            "Inspect the artifact requirements.",
            "Inspect the deployment bindings.",
            "Save the deployment with `bindings` entries that map each logical source.",
            "Use `wf deploy validate <deployment_id>` to confirm the binding set.",
        ],
        related_docs=[
            "docs/workflow_artifacts.md",
            "docs/workflow_capabilities.md#sources",
        ],
    ),
    ExplainCard(
        code="capability_missing",
        summary="A required capability is not present on the bound source.",
        why_it_happens=[
            "The upstream source no longer exposes the tool or node spec.",
            "The workflow was bound to the wrong account/profile/source.",
            "The capability was renamed after the artifact was saved.",
        ],
        how_to_fix=[
            "Run `wf cap list` and search for the expected capability.",
            "Inspect the deployment bindings for the affected logical source.",
            "Rebind to a concrete source that exposes the capability.",
            "Rebuild or patch the artifact if the capability was intentionally renamed.",
        ],
        related_docs=[
            "docs/workflow_capabilities.md",
            "docs/superpowers/specs/2026-06-01-wf-cli-design.md",
        ],
    ),
    ExplainCard(
        code="schema_changed",
        summary="A saved dependency schema no longer matches the live capability.",
        why_it_happens=[
            "The upstream tool or node spec changed its input/output schema.",
            "The deployment is bound to a different source profile than the one used before.",
            "A wrapper assumes fields that the live capability no longer declares.",
        ],
        how_to_fix=[
            "Inspect the live capability.",
            "Compare it with the saved artifact dependency summary.",
            "Patch the draft or wrapper to match the new schema.",
            "Save a new artifact version and deployment after validating the change.",
        ],
        related_docs=[
            "docs/workflow_capabilities.md#dependency-validation",
            "docs/schema_validation.md",
        ],
    ),
    ExplainCard(
        code="deployment_unrunnable",
        summary="The deployment failed validation and should not be run yet.",
        why_it_happens=[
            "One or more required sources, capabilities, schemas, or bindings are invalid.",
            "The deployment points at an artifact version that cannot be resolved.",
            "Live validation found an upstream source or capability problem.",
        ],
        how_to_fix=[
            "Run `wf deploy validate <deployment_id>` and read the diagnostics.",
            "Run `wf explain --input-file <validation-output.json>` for diagnostic details.",
            "Fix source bindings or rebuild the artifact version.",
            "Re-run validation before starting the deployment.",
        ],
        related_docs=[
            "docs/wf_mcp_end_to_end_runbook.md",
            "docs/current_roadmap.md",
        ],
    ),
)
