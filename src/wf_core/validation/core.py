from __future__ import annotations

from wf_core.model import (
    ConditionNode,
    Edge,
    ForeachNode,
    InterruptNode,
    NodeDef,
    NodeUse,
    Step,
    Workflow,
)
from wf_core.tokens import END
from wf_core.validation.issues import ValidationIssueCode, ValidationReport
from wf_core.validation.outcomes import declared_outcomes_for_step, reachable_node_ids
from wf_core.validation.steps import (
    validate_condition_node,
    validate_foreach_node,
    validate_interrupt_node,
    validate_node_use,
)


def validate_workflow(workflow: Workflow) -> ValidationReport:
    report = ValidationReport()

    node_defs = _collect_node_defs(workflow, report)
    nodes_by_id = _validate_nodes(workflow, node_defs, report)
    _validate_start(workflow, nodes_by_id, report)
    outgoing = _validate_edges(workflow.edges, nodes_by_id, node_defs, report)
    _validate_reachable_outcomes(workflow, nodes_by_id, node_defs, outgoing, report)

    return report


def _collect_node_defs(
    workflow: Workflow, report: ValidationReport
) -> dict[str, NodeDef]:
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
    return node_defs


def _validate_nodes(
    workflow: Workflow,
    node_defs: dict[str, NodeDef],
    report: ValidationReport,
) -> dict[str, Step]:
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
            validate_node_use(node, index, node_defs, workflow, report)
        elif isinstance(node, ConditionNode):
            validate_condition_node(
                node, index, report, state_root_fields, input_root_fields
            )
        elif isinstance(node, ForeachNode):
            validate_foreach_node(
                node, index, report, state_root_fields, input_root_fields
            )
        elif isinstance(node, InterruptNode):
            validate_interrupt_node(
                node, index, report, state_root_fields, input_root_fields
            )

    return nodes_by_id


def _validate_start(
    workflow: Workflow,
    nodes_by_id: dict[str, Step],
    report: ValidationReport,
) -> None:
    if workflow.start not in nodes_by_id:
        report.add(
            ValidationIssueCode.UNKNOWN_START,
            "start",
            f"unknown start node {workflow.start!r}",
        )


def _validate_edges(
    edges: list[Edge],
    nodes_by_id: dict[str, Step],
    node_defs: dict[str, NodeDef],
    report: ValidationReport,
) -> dict[str, set[str]]:
    outgoing: dict[str, set[str]] = {}
    edge_keys: set[tuple[str, str]] = set()

    for index, edge in enumerate(edges):
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
            allowed = declared_outcomes_for_step(source, node_defs)
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

    return outgoing


def _validate_reachable_outcomes(
    workflow: Workflow,
    nodes_by_id: dict[str, Step],
    node_defs: dict[str, NodeDef],
    outgoing: dict[str, set[str]],
    report: ValidationReport,
) -> None:
    reachable = reachable_node_ids(workflow.start, workflow.edges, nodes_by_id)

    for node_id in reachable:
        node = nodes_by_id[node_id]
        declared_outcomes = declared_outcomes_for_step(node, node_defs)
        wired = outgoing.get(node_id, set())
        missing = declared_outcomes - wired
        if missing:
            report.add(
                ValidationIssueCode.MISSING_OUTCOME_EDGE,
                f"nodes[{node_id}]",
                f"reachable node is missing edges for outcomes {sorted(missing)!r}",
            )
