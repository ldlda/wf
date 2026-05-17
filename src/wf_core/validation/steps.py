from __future__ import annotations

from wf_core.models.conditions import (
    BinaryCondition,
    Condition,
    ExistsCondition,
    LiteralOperand,
    NotCondition,
    PathOperand,
    VariadicCondition,
)
from wf_core.local_paths import LocalPathError, has_overlapping_paths, split_local_path
from wf_core.models.schemas import NodeDef
from wf_core.models.steps import ConditionNode, ForeachNode, InterruptNode, NodeUse
from wf_core.models.workflow import Workflow
from wf_core.paths import is_valid_destination_path, is_valid_source_path
from wf_core.validation.issues import ValidationIssueCode, ValidationReport


def validate_node_use(
    node: NodeUse,
    index: int,
    node_defs: dict[str, NodeDef],
    workflow: Workflow,
    report: ValidationReport,
) -> None:
    node_def = node_defs.get(node.node)
    if node_def is None:
        report.add(
            ValidationIssueCode.UNKNOWN_NODE_DEF,
            f"nodes[{index}].node",
            f"unknown node def {node.node!r}",
        )
        return

    input_fields = set(node_def.input_schema.properties)
    output_fields = set(node_def.output_schema.properties)
    state_fields = set(workflow.state_schema.fields)
    input_root_fields = set(workflow.input_schema.properties)

    for source_path, destination_field in node.in_map.items():
        try:
            destination_root = split_local_path(destination_field)[0]
        except LocalPathError:
            destination_root = ""
        if destination_root not in input_fields:
            report.add(
                ValidationIssueCode.INVALID_NODE_INPUT_FIELD,
                f"nodes[{index}].in_map[{source_path!r}]",
                f"destination field {destination_field!r} is not declared in node input schema",
            )
        if not is_valid_source_path(
            source_path, state_fields, input_root_fields, allow_context=True
        ):
            report.add(
                ValidationIssueCode.INVALID_SOURCE_PATH,
                f"nodes[{index}].in_map[{source_path!r}]",
                "source path must start with input., state., or context. and reference a declared root field when applicable",
            )

    if has_overlapping_paths(node.in_map.values()):
        report.add(
            ValidationIssueCode.INVALID_NODE_INPUT_FIELD,
            f"nodes[{index}].in_map",
            "in_map has overlapping node-local input paths",
        )

    for source_field, destination_path in node.out_map.items():
        try:
            source_root = split_local_path(source_field)[0]
        except LocalPathError:
            source_root = ""
        if source_root not in output_fields:
            report.add(
                ValidationIssueCode.INVALID_NODE_OUTPUT_FIELD,
                f"nodes[{index}].out_map[{source_field!r}]",
                f"source field {source_field!r} is not declared in node output schema",
            )
        if not is_valid_destination_path(destination_path):
            report.add(
                ValidationIssueCode.INVALID_DESTINATION_PATH,
                f"nodes[{index}].out_map[{source_field!r}]",
                "destination path must start with state.",
            )
    if has_overlapping_paths(node.out_map.values()):
        report.add(
            ValidationIssueCode.INVALID_DESTINATION_PATH,
            f"nodes[{index}].out_map",
            "out_map has overlapping state destination paths",
        )


def validate_condition_node(
    node: ConditionNode,
    index: int,
    report: ValidationReport,
    state_root_fields: set[str],
    input_root_fields: set[str],
) -> None:
    if isinstance(node.check, VariadicCondition) and not node.check.args:
        report.add(
            ValidationIssueCode.EMPTY_CONDITION_ARGS,
            f"nodes[{index}].check.args",
            "condition args must not be empty",
        )
    validate_condition_expr(
        node.check,
        f"nodes[{index}].check",
        report,
        state_root_fields,
        input_root_fields,
    )


def validate_foreach_node(
    node: ForeachNode,
    index: int,
    report: ValidationReport,
    state_root_fields: set[str],
    input_root_fields: set[str],
) -> None:
    if not is_valid_source_path(node.over, state_root_fields, input_root_fields):
        report.add(
            ValidationIssueCode.INVALID_FOREACH_SOURCE,
            f"nodes[{index}].over",
            "foreach source path must start with input. or state. and reference a declared root field",
        )


def validate_interrupt_node(
    node: InterruptNode,
    index: int,
    report: ValidationReport,
    state_root_fields: set[str],
    input_root_fields: set[str],
) -> None:
    for source_path, payload_field in node.request_map.items():
        if not payload_field:
            report.add(
                ValidationIssueCode.INVALID_INTERRUPT_SOURCE,
                f"nodes[{index}].request_map[{source_path!r}]",
                "interrupt request payload field must not be empty",
            )
        if not is_valid_source_path(source_path, state_root_fields, input_root_fields):
            report.add(
                ValidationIssueCode.INVALID_INTERRUPT_SOURCE,
                f"nodes[{index}].request_map[{source_path!r}]",
                "interrupt request source must start with input. or state. and reference a declared root field",
            )

    for resume_field, destination_path in node.out_map.items():
        if not resume_field:
            report.add(
                ValidationIssueCode.INVALID_INTERRUPT_DESTINATION,
                f"nodes[{index}].out_map[{resume_field!r}]",
                "interrupt resume field must not be empty",
            )
        if not is_valid_destination_path(destination_path):
            report.add(
                ValidationIssueCode.INVALID_INTERRUPT_DESTINATION,
                f"nodes[{index}].out_map[{resume_field!r}]",
                "interrupt resume destination must start with state.",
            )


def validate_condition_expr(
    condition: Condition,
    path: str,
    report: ValidationReport,
    state_root_fields: set[str],
    input_root_fields: set[str],
) -> None:
    if isinstance(condition, ExistsCondition):
        if not is_valid_source_path(
            condition.path,
            state_root_fields,
            input_root_fields,
            allow_context=True,
        ):
            report.add(
                ValidationIssueCode.INVALID_CONDITION_PATH,
                path,
                f"invalid condition path {condition.path!r}",
            )
        return

    if isinstance(condition, NotCondition):
        validate_condition_expr(
            condition.arg,
            f"{path}.arg",
            report,
            state_root_fields,
            input_root_fields,
        )
        return

    if isinstance(condition, VariadicCondition):
        for index, arg in enumerate(condition.args):
            validate_condition_expr(
                arg,
                f"{path}.args[{index}]",
                report,
                state_root_fields,
                input_root_fields,
            )
        return

    if isinstance(condition, BinaryCondition):
        validate_operand(
            condition.left,
            f"{path}.left",
            report,
            state_root_fields,
            input_root_fields,
        )
        validate_operand(
            condition.right,
            f"{path}.right",
            report,
            state_root_fields,
            input_root_fields,
        )


def validate_operand(
    operand: PathOperand | LiteralOperand,
    path: str,
    report: ValidationReport,
    state_root_fields: set[str],
    input_root_fields: set[str],
) -> None:
    if isinstance(operand, LiteralOperand):
        return
    if not is_valid_source_path(
        operand.path, state_root_fields, input_root_fields, allow_context=True
    ):
        report.add(
            ValidationIssueCode.INVALID_CONDITION_PATH,
            path,
            f"invalid operand path {operand.path!r}",
        )
