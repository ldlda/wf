"""Compatibility shim for workflow API wrapper authoring hints.

New code should import from `wf_api.wrapper_hints`. This module stays so older
MCP workflow-surface imports keep working until callers migrate.
"""

from wf_api.wrapper_hints import (
    MissingDecision,
    MissingDecisionKind,
    OutcomeCandidate,
    OutcomeCandidateKind,
    WrapperAuthoringHints,
    WrapperHintConfidence,
    WrapperOutcomePolicy,
    workflow_output_schema_for_authoring,
    wrapper_hints_for_capability,
)

__all__ = [
    "MissingDecision",
    "MissingDecisionKind",
    "OutcomeCandidate",
    "OutcomeCandidateKind",
    "WrapperAuthoringHints",
    "WrapperHintConfidence",
    "WrapperOutcomePolicy",
    "workflow_output_schema_for_authoring",
    "wrapper_hints_for_capability",
]
