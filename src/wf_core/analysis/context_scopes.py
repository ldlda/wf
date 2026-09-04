from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Literal

from wf_core.analysis.control_regions import (
    ControlRegionAnalysis,
    ForeachOwnerStack,
    analyze_control_regions,
)
from wf_core.context_contracts import (
    FOREACH_CONTEXT_KEY,
    LOOP_INDEX_CONTEXT_KEY,
    LOOP_ITEM_CONTEXT_KEY,
    RESERVED_CONTEXT_KEYS,
    STANDARD_CONTEXT_FIELDS,
    ContextFieldContract,
    ContextSchema,
    foreach_context_fields,
    foreach_entry_schema,
    structured_foreach_contract,
)
from wf_core.models.steps import ForeachNode
from wf_core.models.workflow import Edge, Workflow
from wf_core.schema_navigation import SchemaNavigator
from wf_core.tokens import END

type ContextAvailability = Literal["available", "conditional"]


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
    *,
    control_regions: ControlRegionAnalysis | None = None,
) -> dict[str, tuple[ContextFieldAvailability, ...]]:
    """Return runtime context contracts for every reachable graph node.

    This is an abstract execution-frame analysis keyed by static control
    region: each node use belongs to exactly one foreach-owner stack, and
    that stack decides which foreach entries the node exposes. A node
    reachable under two stacks is a region conflict and receives no foreach
    fields. The traversal still memoizes node id and owner stack so cyclic
    graphs terminate.
    """
    return _analyze(workflow, control_regions=control_regions).fields_by_node


def context_analysis_warnings(workflow: Workflow) -> tuple[str, ...]:
    """Return bounded warnings found while analyzing workflow frame scopes."""
    return _analyze(workflow).warnings


def context_schemas_by_node(
    workflow: Workflow,
    *,
    control_regions: ControlRegionAnalysis | None = None,
) -> dict[str, ContextSchema]:
    """Return schemas for all unambiguous, reachable program locations.

    A conflicted or unreachable node has no generated per-node schema;
    callers treat that absence as invalid, not as root context. Schemas are
    composed from the same owner-stack analysis as field contracts, not from
    a second graph traversal.
    """
    analysis = control_regions or analyze_control_regions(workflow)
    foreach_nodes = {
        node.id: node for node in workflow.nodes if isinstance(node, ForeachNode)
    }
    schemas: dict[str, ContextSchema] = {}
    for node_id, stack in analysis.owner_stack_by_node.items():
        # Conflicted nodes are already dropped from owner_stack_by_node by the
        # control-region analysis, so every entry here is unambiguous.
        schemas[node_id] = _context_schema_for_stack(
            workflow, foreach_nodes, analysis.owner_stack_by_node, stack
        )
    return schemas


def context_schema_for_node(workflow: Workflow, node_id: str) -> ContextSchema:
    """Return the complete graph-visible context object schema at one node."""
    schemas = context_schemas_by_node(workflow)
    try:
        return schemas[node_id]
    except KeyError as exc:
        raise KeyError(f"no context schema for node {node_id!r}") from exc


def root_context_schema() -> ContextSchema:
    """Return standard fields plus an empty structured foreach map."""
    properties: dict[str, ContextSchema] = {
        field.name: deepcopy(field.schema) for field in STANDARD_CONTEXT_FIELDS
    }
    properties[FOREACH_CONTEXT_KEY] = {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": properties,
        "required": sorted(properties),
        "additionalProperties": False,
    }


def _analyze(
    workflow: Workflow,
    *,
    control_regions: ControlRegionAnalysis | None = None,
) -> _ContextAnalysis:
    """Derive context contracts from static foreach control regions.

    Each unambiguous node use has exactly one owner stack; all active entries
    in that stack are exposed. A canonical return edge pops the stack, so the
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

    analysis = control_regions or analyze_control_regions(workflow)
    for issue in analysis.issues:
        warnings.add(
            f"control region {issue.kind.value} at {issue.path}: {issue.message}"
        )

    fields_by_node: dict[str, tuple[ContextFieldAvailability, ...]] = {}
    for node_id, stack in analysis.owner_stack_by_node.items():
        fields_by_node[node_id] = _available_fields(
            workflow,
            foreach_nodes,
            analysis.owner_stack_by_node,
            stack,
        )
    return _ContextAnalysis(fields_by_node, tuple(warnings.values))


def _available_fields(
    workflow: Workflow,
    foreach_nodes: Mapping[str, ForeachNode],
    owner_stack_by_node: Mapping[str, ForeachOwnerStack],
    stack: ForeachOwnerStack,
) -> tuple[ContextFieldAvailability, ...]:
    """Return contracts for one static owner stack; all are guaranteed.

    A single node use has one control region, so foreach fields are either
    present (inside bodies) or absent (outside). Every owner in the stack
    contributes one required ``foreach.<id>`` entry, every active configured
    alias, and ``loop_item``/``loop_index`` from the final owner only.
    Conditional availability is not used to represent multiple owner stacks:
    a node reached under two stacks is a region conflict and receives no
    foreach fields at all.
    """
    contracts = list(STANDARD_CONTEXT_FIELDS)
    if not stack:
        # The empty foreach map stays readable at root, matching
        # ``root_context_schema`` and the validation pass.
        contracts.append(structured_foreach_contract({}))
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
    entry_schemas: dict[str, ContextSchema] = {}
    for owner_id in stack:
        foreach = foreach_nodes.get(owner_id)
        if foreach is None:
            continue
        entry_schemas[owner_id] = foreach_entry_schema(
            owner_id,
            _foreach_item_schema(
                workflow,
                foreach,
                foreach_nodes,
                owner_stack_by_node,
            ),
        )
    if entry_schemas:
        contracts.append(structured_foreach_contract(entry_schemas))
    # Aliases for every active owner, plus innermost loop keys.
    for owner_id in stack:
        foreach = foreach_nodes.get(owner_id)
        if foreach is None:
            continue
        item_schema = _foreach_item_schema(
            workflow, foreach, foreach_nodes, owner_stack_by_node
        )
        # Only the innermost owner contributes loop_item/loop_index; every
        # owner contributes its configured alias when unambiguous. Alias
        # collision handling is a validation concern; here we expose what the
        # stack declares.
        if owner_id == stack[-1]:
            contracts.extend(foreach_context_fields(foreach.as_, item_schema))
        elif foreach.as_:
            # Outer aliases are exposed without re-emitting loop keys.
            outer_fields = foreach_context_fields(foreach.as_, item_schema)
            for field in outer_fields:
                if field.name not in (LOOP_ITEM_CONTEXT_KEY, LOOP_INDEX_CONTEXT_KEY):
                    contracts.append(field)
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


def _context_schema_for_stack(
    workflow: Workflow,
    foreach_nodes: Mapping[str, ForeachNode],
    owner_stack_by_node: Mapping[str, ForeachOwnerStack],
    stack: ForeachOwnerStack,
) -> ContextSchema:
    """Build the complete graph-visible context object schema for one stack."""
    properties: dict[str, ContextSchema] = {
        field.name: deepcopy(field.schema) for field in STANDARD_CONTEXT_FIELDS
    }
    entry_schemas: dict[str, ContextSchema] = {}
    for owner_id in stack:
        foreach = foreach_nodes.get(owner_id)
        if foreach is None:
            continue
        entry_schemas[owner_id] = foreach_entry_schema(
            owner_id,
            _foreach_item_schema(workflow, foreach, foreach_nodes, owner_stack_by_node),
        )
    properties[FOREACH_CONTEXT_KEY] = {
        "type": "object",
        "properties": entry_schemas,
        "required": sorted(entry_schemas),
        "additionalProperties": False,
    }
    required: list[str] = [field.name for field in STANDARD_CONTEXT_FIELDS] + [
        FOREACH_CONTEXT_KEY
    ]
    if stack:
        innermost = foreach_nodes.get(stack[-1])
        if innermost is not None:
            inner_item = _foreach_item_schema(
                workflow, innermost, foreach_nodes, owner_stack_by_node
            )
            properties[LOOP_ITEM_CONTEXT_KEY] = deepcopy(inner_item)
            properties[LOOP_INDEX_CONTEXT_KEY] = {"type": "integer"}
            required.extend([LOOP_ITEM_CONTEXT_KEY, LOOP_INDEX_CONTEXT_KEY])
        for owner_id in stack:
            foreach = foreach_nodes.get(owner_id)
            if (
                foreach is not None
                and foreach.as_
                and foreach.as_ not in RESERVED_CONTEXT_KEYS
            ):
                properties[foreach.as_] = deepcopy(
                    _foreach_item_schema(
                        workflow, foreach, foreach_nodes, owner_stack_by_node
                    )
                )
                required.append(foreach.as_)
    # Deduplicate while preserving order; aliases could theoretically repeat
    # a standard name, but validation rejects those collisions.
    seen: set[str] = set()
    deduped_required: list[str] = []
    for name in required:
        if name not in seen:
            seen.add(name)
            deduped_required.append(name)
    return {
        "type": "object",
        "properties": properties,
        "required": sorted(deduped_required),
        "additionalProperties": False,
    }


def _foreach_item_schema(
    workflow: Workflow,
    foreach: ForeachNode,
    foreach_nodes: Mapping[str, ForeachNode],
    owner_stack_by_node: Mapping[str, ForeachOwnerStack],
) -> ContextSchema:
    """Resolve one controller's item schema in its own static context.

    An inner foreach may declare ``over="context.foreach.outer.item.children"``;
    the lookup uses the controller's own owner stack, not the inner body stack.
    """
    controller_stack = owner_stack_by_node.get(foreach.id)
    if controller_stack is None:
        return {}
    document = _schema_document(
        workflow,
        foreach.over.root,
        stack=controller_stack,
        foreach_nodes=foreach_nodes,
        owner_stack_by_node=owner_stack_by_node,
    )
    source = SchemaNavigator(document).at_path(foreach.over.parts)
    if source is None:
        return {}
    items = source.array_items()
    if items is None:
        return {}
    return items.standalone_schema()


def _schema_document(
    workflow: Workflow,
    root: str,
    *,
    stack: ForeachOwnerStack | None = None,
    foreach_nodes: Mapping[str, ForeachNode] | None = None,
    owner_stack_by_node: Mapping[str, ForeachOwnerStack] | None = None,
) -> Mapping[str, object]:
    if root == "input":
        return workflow.input_schema.model_dump(mode="json", exclude_none=True)
    if root == "state":
        return workflow.state_schema.model_dump(mode="json", exclude_none=True)
    if root == "context":
        resolved_stack: ForeachOwnerStack = stack or ()
        current: dict[str, object] = {
            field.name: field.schema for field in STANDARD_CONTEXT_FIELDS
        }
        if foreach_nodes is not None and owner_stack_by_node is not None:
            entry_schemas: dict[str, object] = {}
            for owner_id in resolved_stack:
                foreach = foreach_nodes.get(owner_id)
                if foreach is not None:
                    entry_schemas[owner_id] = foreach_entry_schema(
                        owner_id,
                        _foreach_item_schema(
                            workflow,
                            foreach,
                            foreach_nodes,
                            owner_stack_by_node,
                        ),
                    )
            current[FOREACH_CONTEXT_KEY] = {
                "type": "object",
                "properties": entry_schemas,
                "required": sorted(entry_schemas),
                "additionalProperties": False,
            }
            for owner_id in resolved_stack:
                foreach = foreach_nodes.get(owner_id)
                if foreach is not None:
                    item_schema = _foreach_item_schema(
                        workflow,
                        foreach,
                        foreach_nodes,
                        owner_stack_by_node,
                    )
                    for field in foreach_context_fields(foreach.as_, item_schema):
                        # Innermost loop keys win; outer aliases accumulate.
                        # Validation owns collision diagnostics.
                        is_innermost = (
                            bool(resolved_stack) and owner_id == resolved_stack[-1]
                        )
                        if field.name not in current or is_innermost:
                            current[field.name] = field.schema
        return {"type": "object", "properties": current}
    return {}
