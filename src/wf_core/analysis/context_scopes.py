from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Literal

from wf_core.analysis.control_regions import (
    ForeachOwnerStack,
    analyze_control_regions,
)
from wf_core.context_contracts import (
    STANDARD_CONTEXT_FIELDS,
    ContextFieldContract,
    ContextSchema,
    foreach_context_fields,
)
from wf_core.models.steps import ForeachNode
from wf_core.models.workflow import Edge, Workflow
from wf_core.tokens import END

type ContextAvailability = Literal["available", "conditional"]
type FrameScope = str | None

_MAX_LOCAL_SCHEMA_REFERENCE_DEPTH = 32


@dataclass(frozen=True, slots=True)
class ContextFieldAvailability:
    """One context contract plus whether it is guaranteed at a graph node."""

    contract: ContextFieldContract
    availability: ContextAvailability
    reason: str | None = None

    @property
    def name(self) -> str:
        return self.contract.name

    @property
    def schema(self) -> ContextSchema:
        return self.contract.schema

    @property
    def description(self) -> str:
        return self.contract.description


@dataclass(slots=True)
class _ContextAnalysis:
    fields_by_node: dict[str, tuple[ContextFieldAvailability, ...]]
    warnings: tuple[str, ...]


class _Warnings:
    def __init__(self) -> None:
        self.values: list[str] = []
        self.seen: set[str] = set()

    def add(self, value: str) -> None:
        if value not in self.seen:
            self.seen.add(value)
            self.values.append(value)


def context_fields_by_node(
    workflow: Workflow,
) -> dict[str, tuple[ContextFieldAvailability, ...]]:
    """Return runtime context contracts for every reachable graph node.

    This is an abstract execution-frame analysis rather than ordinary graph
    reachability: the same node can execute in the root frame and in a
    foreach child frame, and those frames expose different context keys.
    The traversal memoizes both node id and active frame scope so cyclic
    graphs terminate without granting aliases from an impossible scope.
    """
    return _analyze(workflow).fields_by_node


def context_analysis_warnings(workflow: Workflow) -> tuple[str, ...]:
    """Return bounded warnings found while analyzing workflow frame scopes."""
    return _analyze(workflow).warnings


def _analyze(workflow: Workflow) -> _ContextAnalysis:
    """Derive context contracts from static foreach control regions.

    Each unambiguous node use has exactly one owner stack; its active foreach
    is the final stack item. A canonical return edge pops the stack, so the
    controller itself stays in the outer context. Conflicted nodes receive no
    foreach fields.
    """
    nodes = {node.id: node for node in workflow.nodes}
    foreach_nodes = {
        node.id: node for node in workflow.nodes if isinstance(node, ForeachNode)
    }
    edges_by_node: dict[str, list[Edge]] = {}
    warnings = _Warnings()

    for edge in workflow.edges:
        edges_by_node.setdefault(edge.from_, []).append(edge)
        if edge.from_ not in nodes:
            warnings.add(f"edge source {edge.from_!r} is not a workflow node")
        if edge.to != END and edge.to not in nodes:
            warnings.add(f"edge from {edge.from_!r} targets missing node {edge.to!r}")

    for foreach in foreach_nodes.values():
        if not any(
            edge.outcome == "loop" for edge in edges_by_node.get(foreach.id, [])
        ):
            warnings.add(
                f"foreach node {foreach.id!r} has no loop route; "
                "no scoped alias is guaranteed"
            )

    if workflow.start not in nodes:
        warnings.add(f"workflow start targets missing node {workflow.start!r}")
        return _ContextAnalysis({}, tuple(warnings.values))

    analysis = analyze_control_regions(workflow)
    for issue in analysis.issues:
        warnings.add(
            f"control region {issue.kind.value} at {issue.path}: {issue.message}"
        )

    fields_by_node: dict[str, tuple[ContextFieldAvailability, ...]] = {}
    for node_id, stack in analysis.owner_stack_by_node.items():
        active_foreach_id = stack[-1] if stack else None
        fields_by_node[node_id] = _available_fields(
            workflow,
            foreach_nodes,
            analysis.owner_stack_by_node,
            active_foreach_id,
        )
    return _ContextAnalysis(fields_by_node, tuple(warnings.values))


def _available_fields(
    workflow: Workflow,
    foreach_nodes: Mapping[str, ForeachNode],
    owner_stack_by_node: Mapping[str, ForeachOwnerStack],
    active_scope: FrameScope,
) -> tuple[ContextFieldAvailability, ...]:
    """Return contracts for one static owner stack; all are guaranteed.

    A single node use has one control region, so foreach fields are either
    present (inside a body) or absent (outside). Conditional availability is
    not used to represent multiple owner stacks: a node reached under two
    stacks is a region conflict and receives no foreach fields at all.
    """
    contracts = list(STANDARD_CONTEXT_FIELDS)
    if active_scope is not None:
        foreach = foreach_nodes.get(active_scope)
        if foreach is not None:
            contracts.extend(
                foreach_context_fields(
                    foreach.as_,
                    _foreach_item_schema(
                        workflow,
                        foreach,
                        foreach_nodes,
                        owner_stack_by_node,
                    ),
                )
            )
    return tuple(
        ContextFieldAvailability(
            contract=ContextFieldContract(
                contract.name,
                deepcopy(contract.schema),
                contract.description,
            ),
            availability="available",
        )
        for contract in contracts
    )


def _foreach_item_schema(
    workflow: Workflow,
    foreach: ForeachNode,
    foreach_nodes: Mapping[str, ForeachNode],
    owner_stack_by_node: Mapping[str, ForeachOwnerStack],
) -> ContextSchema:
    """Resolve one controller's item schema in its own static context.

    An inner foreach may declare ``over="context.outer_item"``; the lookup
    uses the controller's own owner stack, not the inner body stack.
    """
    controller_stack = owner_stack_by_node.get(foreach.id)
    if controller_stack is None:
        return {}
    controller_scope: FrameScope = controller_stack[-1] if controller_stack else None
    source_schema = _schema_at_path(
        workflow,
        foreach.over.root,
        foreach.over.parts,
        controller_scope,
        foreach_nodes,
        owner_stack_by_node,
    )
    if not isinstance(source_schema, Mapping):
        return {}
    source_type = source_schema.get("type")
    is_array = source_type == "array" or (
        isinstance(source_type, list) and "array" in source_type
    )
    items = source_schema.get("items")
    if not is_array or not isinstance(items, Mapping):
        return {}
    try:
        resolved_items = _resolve_local_reference(
            _schema_document(
                workflow,
                foreach.over.root,
                foreach_nodes=foreach_nodes,
                owner_stack_by_node=owner_stack_by_node,
            ),
            items,
        )
    except ValueError:
        return {}
    return deepcopy(dict(resolved_items))


def _schema_at_path(
    workflow: Workflow,
    root: str,
    parts: tuple[str, ...],
    active_scope: FrameScope,
    foreach_nodes: Mapping[str, ForeachNode],
    owner_stack_by_node: Mapping[str, ForeachOwnerStack],
) -> Mapping[str, object] | None:
    try:
        schema_document = _schema_document(
            workflow,
            root,
            active_scope=active_scope,
            foreach_nodes=foreach_nodes,
            owner_stack_by_node=owner_stack_by_node,
        )
        current: object = schema_document
        for part in parts:
            if not isinstance(current, Mapping):
                return None
            resolved = _resolve_local_reference(schema_document, current)
            properties = resolved.get("properties")
            if not isinstance(properties, Mapping):
                return None
            current = properties.get(part)
        if not isinstance(current, Mapping):
            return None
        return _resolve_local_reference(schema_document, current)
    except ValueError:
        return None


def _schema_document(
    workflow: Workflow,
    root: str,
    *,
    active_scope: FrameScope = None,
    foreach_nodes: Mapping[str, ForeachNode] | None = None,
    owner_stack_by_node: Mapping[str, ForeachOwnerStack] | None = None,
) -> Mapping[str, object]:
    if root == "input":
        return workflow.input_schema.model_dump(mode="json", exclude_none=True)
    if root == "state":
        return workflow.state_schema.model_dump(mode="json", exclude_none=True)
    if root == "context":
        current: dict[str, object] = {
            field.name: field.schema for field in STANDARD_CONTEXT_FIELDS
        }
        if (
            active_scope is not None
            and foreach_nodes is not None
            and owner_stack_by_node is not None
        ):
            foreach = foreach_nodes.get(active_scope)
            if foreach is not None:
                current.update(
                    {
                        field.name: field.schema
                        for field in foreach_context_fields(
                            foreach.as_,
                            _foreach_item_schema(
                                workflow,
                                foreach,
                                foreach_nodes,
                                owner_stack_by_node,
                            ),
                        )
                    }
                )
        return {"type": "object", "properties": current}
    return {}


def _resolve_local_reference(
    root_schema: Mapping[str, object],
    candidate: Mapping[str, object],
) -> Mapping[str, object]:
    """Resolve bounded repository-local refs without becoming a full resolver."""
    current = candidate
    seen: set[str] = set()
    while "$ref" in current:
        reference = current["$ref"]
        if not isinstance(reference, str):
            raise ValueError("schema reference must be a string")
        if reference in seen:
            raise ValueError(f"cyclic schema reference {reference!r}")
        if len(seen) >= _MAX_LOCAL_SCHEMA_REFERENCE_DEPTH:
            raise ValueError(
                f"local schema reference depth exceeds "
                f"{_MAX_LOCAL_SCHEMA_REFERENCE_DEPTH}"
            )
        if not (
            reference.startswith("#/$defs/") or reference.startswith("#/definitions/")
        ):
            raise ValueError(f"unsupported schema reference {reference!r}")
        seen.add(reference)
        resolved: object = root_schema
        for raw_part in reference.removeprefix("#/").split("/"):
            part = raw_part.replace("~1", "/").replace("~0", "~")
            if not isinstance(resolved, Mapping) or part not in resolved:
                raise ValueError(f"unresolved schema reference {reference!r}")
            resolved = resolved[part]
        if not isinstance(resolved, Mapping):
            raise ValueError(f"schema reference {reference!r} is not an object")
        current = resolved
    return current
