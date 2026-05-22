from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ValidationIssueCode(StrEnum):
    DUPLICATE_NODE_DEF = "duplicate_node_def"
    DUPLICATE_NODE_ID = "duplicate_node_id"
    UNKNOWN_START = "unknown_start"
    DUPLICATE_EDGE = "duplicate_edge"
    UNKNOWN_EDGE_SOURCE = "unknown_edge_source"
    UNKNOWN_EDGE_DESTINATION = "unknown_edge_destination"
    UNDECLARED_EDGE_OUTCOME = "undeclared_edge_outcome"
    MISSING_OUTCOME_EDGE = "missing_outcome_edge"
    UNKNOWN_NODE_DEF = "unknown_node_def"
    INVALID_NODE_INPUT_FIELD = "invalid_node_input_field"
    INVALID_SOURCE_PATH = "invalid_source_path"
    INVALID_NODE_OUTPUT_FIELD = "invalid_node_output_field"
    INVALID_DESTINATION_PATH = "invalid_destination_path"
    EMPTY_CONDITION_ARGS = "empty_condition_args"
    INVALID_CONDITION_PATH = "invalid_condition_path"
    INVALID_FOREACH_SOURCE = "invalid_foreach_source"
    INVALID_FOREACH_COLLECT_DESTINATION = "invalid_foreach_collect_destination"
    INVALID_INTERRUPT_SOURCE = "invalid_interrupt_source"
    INVALID_INTERRUPT_DESTINATION = "invalid_interrupt_destination"


@dataclass(slots=True)
class ValidationIssue:
    code: ValidationIssueCode
    path: str
    message: str


@dataclass(slots=True)
class ValidationReport:
    errors: list[ValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def add(self, code: ValidationIssueCode, path: str, message: str) -> None:
        self.errors.append(ValidationIssue(code=code, path=path, message=message))

    def raise_for_errors(self) -> None:
        if not self.errors:
            return
        rendered = "\n".join(
            f"- [{issue.code}] {issue.path}: {issue.message}" for issue in self.errors
        )
        raise ValueError(f"Workflow validation failed:\n{rendered}")
