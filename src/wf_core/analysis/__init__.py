"""Static analyses over workflow graph contracts."""

from .context_scopes import (
    ContextFieldAvailability,
    context_analysis_warnings,
    context_fields_by_node,
    context_schema_for_node,
    context_schemas_by_node,
    root_context_schema,
)
from .control_regions import (
    ControlRegionAnalysis,
    ControlRegionIssue,
    ControlRegionIssueKind,
    ForeachOwnerStack,
    analyze_control_regions,
)

__all__ = [
    "ContextFieldAvailability",
    "ControlRegionAnalysis",
    "ControlRegionIssue",
    "ControlRegionIssueKind",
    "ForeachOwnerStack",
    "analyze_control_regions",
    "context_analysis_warnings",
    "context_fields_by_node",
    "context_schema_for_node",
    "context_schemas_by_node",
    "root_context_schema",
]
