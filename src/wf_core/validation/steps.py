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
from wf_core.models.steps import (
    ConditionNode,
    ForeachNode,
    InputPathBinding,
    InterruptNode,
    NodeUse,
)
from wf_core.models.workflow import Workflow
from wf_core.paths import (
    LocalPath,
    PathResolutionError,
    StatePath,
    is_valid_destination_path,
    is_valid_source_path,
)
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
    state_root_fields = {field.split(".", maxsplit=1)[0] for field in state_fields}
    input_root_fields = set(workflow.input_schema.properties)

    input_targets = []
    for input_index, binding in enumerate(node.input):
        input_targets.append(binding.target)
        destination_root = _local_root(binding.target)
        if destination_root is None or (
            destination_root != "." and destination_root not in input_fields
        ):
            report.add(
                ValidationIssueCode.INVALID_NODE_INPUT_FIELD,
                f"nodes[{index}].input[{input_index}].target",
                f"destination field {str(binding.target)!r} is not declared in node input schema",
            )

        if isinstance(binding, InputPathBinding) and not is_valid_source_path(
            binding.path, state_root_fields, input_root_fields, allow_context=True
        ):
            report.add(
                ValidationIssueCode.INVALID_SOURCE_PATH,
                f"nodes[{index}].input[{input_index}].path",
                "source path must start with input., state., or context. and reference a declared root field when applicable",
            )

    if has_overlapping_paths(input_targets):
        report.add(
            ValidationIssueCode.INVALID_NODE_INPUT_FIELD,
            f"nodes[{index}].input",
            "input has overlapping node-local input paths",
        )

    output_targets = []
    for output_index, binding in enumerate(node.output):
        output_targets.append(str(binding.target))
        source_root = _local_root(binding.source)
        if source_root is None or (
            source_root != "." and source_root not in output_fields
        ):
            report.add(
                ValidationIssueCode.INVALID_NODE_OUTPUT_FIELD,
                f"nodes[{index}].output[{output_index}].source",
                f"source field {str(binding.source)!r} is not declared in node output schema",
            )
        destination_root = _state_destination_root(binding.target)
        if destination_root is None or destination_root not in state_root_fields:
            report.add(
                ValidationIssueCode.INVALID_DESTINATION_PATH,
                f"nodes[{index}].output[{output_index}].target",
                "destination path must start with state. and reference a declared root field",
            )
    if has_overlapping_paths(output_targets):
        report.add(
            ValidationIssueCode.INVALID_DESTINATION_PATH,
            f"nodes[{index}].output",
            "output has overlapping state destination paths",
        )


def _local_root(path: str | LocalPath) -> str | None:
    try:
        parts = split_local_path(path)
    except LocalPathError:
        return None
    return "." if not parts else parts[0]


def _state_destination_root(path: object) -> str | None:
    try:
        return StatePath.parse(str(path)).parts[0]
    except PathResolutionError:
        return None


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
