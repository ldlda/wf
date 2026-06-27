from __future__ import annotations

from wf_artifacts.draft_workspaces.api import REVISION_CONFLICT_CODE
from wf_artifacts.drafts.api import (
    DRAFT_INVALID_CODE,
    PATCH_INVALID_CODE,
    UNKNOWN_OUTCOME_CODE,
)
from wf_core.validation.issues import ValidationIssueCode

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
            "docs/wf_cli.md#common-diagnostics",
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
            "docs/wf_cli.md#deployments",
            "docs/wf_mcp_troubleshooting.md",
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
            "docs/wf_cli.md#deployments",
            "docs/workflow_artifacts.md",
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
            "docs/wf_cli.md#capability-discovery",
            "docs/workflow_capabilities.md",
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
            "docs/wf_cli.md#common-diagnostics",
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
            "docs/wf_cli.md#common-diagnostics",
            "docs/current_roadmap.md",
        ],
    ),
    ExplainCard(
        code=ValidationIssueCode.INVALID_SOURCE_PATH.value,
        summary="A workflow step reads from a path that is not declared or available.",
        why_it_happens=[
            "A step input binding points at input/state/context data that the draft schema does not declare.",
            "A literal placeholder or guessed path was used in a binding.",
            "A wrapper bootstrap included a field that is not present in the actual run input.",
        ],
        how_to_fix=[
            "Run `wf schema InputPathBinding` to confirm binding shape.",
            "Inspect the draft input and state schemas.",
            "Use `wf draft set-input --merge` to repair step input bindings.",
            "Patch the draft input_schema/state_schema when the workflow genuinely needs a new path.",
            "Run `wf draft validate <workspace_id>` after the edit.",
        ],
        related_docs=[
            "docs/wf_cli.md#draft-workspaces",
            "docs/workflow_drafts.md",
        ],
    ),
    ExplainCard(
        code=ValidationIssueCode.INVALID_DESTINATION_PATH.value,
        summary="A workflow step writes to a state or output path that is not declared.",
        why_it_happens=[
            "A capability output is bound to a missing state_schema field.",
            "A workflow output projection points at a missing output_schema field.",
            "A draft patch changed output bindings without changing the matching schema.",
        ],
        how_to_fix=[
            "For capability output to state, prefer `wf draft bind --from local.FIELD --to state.FIELD`.",
            "For multiple output bindings, use `wf draft set-output --merge` when preserving existing mappings.",
            "Read any `repair_hint` returned by `wf draft validate` before writing JSON Patch.",
            "Run `wf draft validate <workspace_id>` after the edit.",
        ],
        related_docs=[
            "docs/wf_cli.md#draft-workspaces",
            "docs/workflow_drafts.md",
        ],
    ),
    ExplainCard(
        code=ValidationIssueCode.UNKNOWN_EDGE_DESTINATION.value,
        summary="A route or edge points at a step id that does not exist in the workflow.",
        why_it_happens=[
            "A draft route was added before the target step was created.",
            "A step id was misspelled in a route or edge.",
            "A raw plan edge references a node id that is absent from `nodes`.",
        ],
        how_to_fix=[
            "In draft authoring, create the target step first, then route to it.",
            "Use `wf draft handle <workspace_id> --step FROM --outcome OUTCOME --to TARGET` to repair one route.",
            "Use `wf draft branch <workspace_id> --step FROM --route OUTCOME=TARGET` for multiple route edits.",
            "For a complete graph authored at once, prefer `wf artifact create-from-plan` and validate the raw plan shape.",
        ],
        related_docs=[
            "docs/wf_cli.md#draft-workspaces",
            "docs/workflow_drafts.md",
        ],
    ),
    ExplainCard(
        code=ValidationIssueCode.UNDECLARED_EDGE_OUTCOME.value,
        summary="A route uses an outcome that the source step does not declare.",
        why_it_happens=[
            "The route outcome was guessed instead of read from capability metadata.",
            "A multi-outcome capability was wired with an incomplete or misspelled outcome map.",
        ],
        how_to_fix=[
            "Run `wf cap inspect <capability>` and read the declared outcomes.",
            "Use `wf draft handle` or `wf draft branch` with the exact outcome names.",
            "Run `wf draft validate <workspace_id>` after route edits.",
        ],
        related_docs=[
            "docs/wf_cli.md#draft-workspaces",
            "docs/workflow_capabilities.md",
        ],
    ),
    ExplainCard(
        code=ValidationIssueCode.MISSING_OUTCOME_EDGE.value,
        summary="A step outcome has no route and the workflow cannot prove where execution goes next.",
        why_it_happens=[
            "A multi-outcome step was added without complete route coverage.",
            "A draft patch replaced a route map and dropped an existing outcome.",
        ],
        how_to_fix=[
            "Run `wf cap inspect <capability>` to list declared outcomes.",
            "Use `wf draft branch --route OUTCOME=TARGET` for each missing outcome.",
            "Route terminal outcomes to `__end__` when the workflow should finish.",
        ],
        related_docs=[
            "docs/wf_cli.md#draft-workspaces",
            "docs/workflow_drafts.md",
        ],
    ),
    ExplainCard(
        code=UNKNOWN_OUTCOME_CODE,
        summary="A draft route uses an outcome that the source step cannot produce.",
        why_it_happens=[
            "The route outcome was guessed instead of read from the capability contract.",
            "A draft patch preserved an old outcome after the step capability changed.",
        ],
        how_to_fix=[
            "Run `wf cap inspect <capability>` and read the declared outcomes.",
            "Use `wf draft handle <workspace_id> --step STEP --outcome OUTCOME --to TARGET` with a declared outcome.",
            "Use `wf draft branch <workspace_id> --step STEP --route OUTCOME=TARGET` when repairing multiple outcomes.",
            "Run `wf draft validate <workspace_id>` after route edits.",
        ],
        related_docs=[
            "docs/wf_cli.md#draft-workspaces",
            "docs/workflow_drafts.md",
        ],
    ),
    ExplainCard(
        code=DRAFT_INVALID_CODE,
        summary="A draft workspace contains an invalid draft shape or invalid workflow structure.",
        why_it_happens=[
            "The payload mixed draft-workspace shape with raw-plan shape.",
            "A JSON Patch produced a draft that does not satisfy the draft model.",
            "The draft model is syntactically valid but workflow validation found structural issues.",
        ],
        how_to_fix=[
            "Run `wf schema draft` for draft workspace payloads.",
            "Run `wf schema raw` for `wf artifact create-from-plan` payloads.",
            "Run `wf draft validate <workspace_id>` and follow each diagnostic code.",
            "Use `wf explain <code>` for the nested diagnostics before patching again.",
        ],
        related_docs=[
            "docs/wf_cli.md#draft-workspaces",
            "docs/workflow_drafts.md",
        ],
    ),
    ExplainCard(
        code=PATCH_INVALID_CODE,
        summary="A draft patch is not a valid RFC 6902 JSON Patch or cannot be applied.",
        why_it_happens=[
            "The patch file used raw draft JSON instead of a JSON Patch operation list.",
            "A patch path points at a missing parent object.",
            "A patch operation is malformed or unsupported by the patch library.",
        ],
        how_to_fix=[
            "Use focused commands such as `wf draft set-input`, `wf draft set-output`, `wf draft bind`, `wf draft handle`, and `wf draft branch` when possible.",
            "If using `wf draft patch`, make the file a JSON array of RFC 6902 operations.",
            "Run `wf schema draft` to inspect the draft shape before choosing patch paths.",
            "Retry with the current workspace revision.",
        ],
        related_docs=[
            "docs/wf_cli.md#draft-workspaces",
            "docs/workflow_drafts.md",
        ],
    ),
    ExplainCard(
        code=REVISION_CONFLICT_CODE,
        summary="A draft command used a stale workspace revision.",
        why_it_happens=[
            "Another edit advanced the draft workspace revision.",
            "The command was retried with an old `--revision` value.",
            "An agent copied a prior command transcript without fetching the current workspace.",
        ],
        how_to_fix=[
            "Run `wf draft inspect <workspace_id>` to get the current revision.",
            "Repeat the edit with the current `--revision` value.",
            "Do not skip revision checks; they prevent overwriting another edit.",
        ],
        related_docs=[
            "docs/wf_cli.md#draft-workspaces",
            "docs/workflow_drafts.md",
        ],
    ),
)
