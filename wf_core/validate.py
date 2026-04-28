from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from .model import (
    BinaryCondition,
    Condition,
    ConditionNode,
    Edge,
    ExistsCondition,
    ForeachNode,
    InterruptNode,
    LiteralOperand,
    NodeDef,
    NodeUse,
    NotCondition,
    PathOperand,
    Step,
    VariadicCondition,
    Workflow,
)
from .paths import is_valid_destination_path, is_valid_source_path
from .tokens import END


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


def validate_workflow(workflow: Workflow) -> ValidationReport:
    report = ValidationReport()

    node_defs: dict[str, NodeDef] = {}
    for index, node_def in enumerate(workflow.node_defs):
        if node_def.name in node_defs:
            report.add(
                ValidationIssueCode.DUPLICATE_NODE_DEF,
                f"node_defs[{index}].name",
                f"duplicate node def name {node_def.name!r}",
            )
        else:
            node_defs[node_def.name] = node_def

    nodes_by_id: dict[str, Step] = {}
    state_root_fields = set(workflow.state_schema.fields)
    input_root_fields = set(workflow.input_schema.properties)

    for index, node in enumerate(workflow.nodes):
        if node.id in nodes_by_id:
            report.add(
                ValidationIssueCode.DUPLICATE_NODE_ID,
                f"nodes[{index}].id",
                f"duplicate node id {node.id!r}",
            )
        else:
            nodes_by_id[node.id] = node

        if isinstance(node, NodeUse):
            _validate_node_use(node, index, node_defs, workflow, report)
        elif isinstance(node, ConditionNode):
            _validate_condition_node(
                node, index, report, state_root_fields, input_root_fields
            )
        elif isinstance(node, ForeachNode):
            _validate_foreach_node(
                node, index, report, state_root_fields, input_root_fields
            )
        elif isinstance(node, InterruptNode):
            _validate_interrupt_node(
                node, index, report, state_root_fields, input_root_fields
            )

    if workflow.start not in nodes_by_id:
        report.add(
            ValidationIssueCode.UNKNOWN_START,
            "start",
            f"unknown start node {workflow.start!r}",
        )

    outgoing: dict[str, set[str]] = {}
    edge_keys: set[tuple[str, str]] = set()

    for index, edge in enumerate(workflow.edges):
        edge_key = (edge.from_, edge.outcome)
        if edge_key in edge_keys:
            report.add(
                ValidationIssueCode.DUPLICATE_EDGE,
                f"edges[{index}]",
                f"duplicate edge for source {edge.from_!r} and outcome {edge.outcome!r}",
            )
        else:
            edge_keys.add(edge_key)

        source = nodes_by_id.get(edge.from_)
        if source is None:
            report.add(
                ValidationIssueCode.UNKNOWN_EDGE_SOURCE,
                f"edges[{index}].from",
                f"unknown source node {edge.from_!r}",
            )
        else:
            allowed = _declared_outcomes_for_step(source, node_defs)
            if edge.outcome not in allowed:
                report.add(
                    ValidationIssueCode.UNDECLARED_EDGE_OUTCOME,
                    f"edges[{index}].outcome",
                    f"outcome {edge.outcome!r} is not declared by node {edge.from_!r}",
                )
            outgoing.setdefault(edge.from_, set()).add(edge.outcome)

        if edge.to != END and edge.to not in nodes_by_id:
            report.add(
                ValidationIssueCode.UNKNOWN_EDGE_DESTINATION,
                f"edges[{index}].to",
                f"unknown destination node {edge.to!r}",
            )

    reachable = _reachable_node_ids(workflow.start, workflow.edges, nodes_by_id)

    for node_id in reachable:
        node = nodes_by_id[node_id]
        declared_outcomes = _declared_outcomes_for_step(node, node_defs)
        wired = outgoing.get(node_id, set())
        missing = declared_outcomes - wired
        if missing:
            report.add(
                ValidationIssueCode.MISSING_OUTCOME_EDGE,
                f"nodes[{node_id}]",
                f"reachable node is missing edges for outcomes {sorted(missing)!r}",
            )

    return report


def _validate_node_use(
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
        if destination_field not in input_fields:
            report.add(
                ValidationIssueCode.INVALID_NODE_INPUT_FIELD,
                f"nodes[{index}].in_map[{source_path!r}]",
                f"destination field {destination_field!r} is not declared in node input schema",
            )
        if not is_valid_source_path(source_path, state_fields, input_root_fields):
            report.add(
                ValidationIssueCode.INVALID_SOURCE_PATH,
                f"nodes[{index}].in_map[{source_path!r}]",
                "source path must start with input. or state. and reference a declared root field",
            )

    for source_field, destination_path in node.out_map.items():
        if source_field not in output_fields:
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


def _validate_condition_node(
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
    _validate_condition_expr(
        node.check,
        f"nodes[{index}].check",
        report,
        state_root_fields,
        input_root_fields,
    )


def _validate_foreach_node(
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


def _validate_interrupt_node(
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


def _validate_condition_expr(
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
        _validate_condition_expr(
            condition.arg,
            f"{path}.arg",
            report,
            state_root_fields,
            input_root_fields,
        )
        return

    if isinstance(condition, VariadicCondition):
        for index, arg in enumerate(condition.args):
            _validate_condition_expr(
                arg,
                f"{path}.args[{index}]",
                report,
                state_root_fields,
                input_root_fields,
            )
        return

    if isinstance(condition, BinaryCondition):
        _validate_operand(
            condition.left,
            f"{path}.left",
            report,
            state_root_fields,
            input_root_fields,
        )
        _validate_operand(
            condition.right,
            f"{path}.right",
            report,
            state_root_fields,
            input_root_fields,
        )


def _validate_operand(
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


def _declared_outcomes_for_step(step: Step, node_defs: dict[str, NodeDef]) -> set[str]:
    if isinstance(step, NodeUse):
        node_def = node_defs.get(step.node)
        return set(node_def.outcomes) if node_def else set()
    if step.type == "condition":
        return {"true", "false"}
    if step.type == "foreach":
        return {"done"}
    if step.type == "join":
        return {"done"}
    if step.type == "interrupt":
        return set(step.outcomes)
    return set()


def _reachable_node_ids(
    start: str, edges: list[Edge], nodes_by_id: dict[str, Step]
) -> set[str]:
    if start not in nodes_by_id:
        return set()

    adjacency: dict[str, list[str]] = {}
    for edge in edges:
        if edge.to == END:
            continue
        adjacency.setdefault(edge.from_, []).append(edge.to)

    seen: set[str] = set()
    stack = [start]
    while stack:
        node_id = stack.pop()
        if node_id in seen:
            continue
        seen.add(node_id)
        stack.extend(adjacency.get(node_id, []))
    return seen
