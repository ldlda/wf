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
    STANDARD_CONTEXT_FIELDS,
    ContextFieldContract,
    ContextSchema,
    foreach_context_fields,
    foreach_entry_schema,
    structured_foreach_contract,
)
from wf_core.models.steps import ForeachNode
from wf_core.models.workflow import Edge, Workflow
from wf_core.tokens import END

type ContextAvailability = Literal["available", "conditional"]

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
            if foreach is not None and foreach.as_:
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
    source_schema = _schema_at_path(
        workflow,
        foreach.over.root,
        foreach.over.parts,
        controller_stack,
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
    document = _schema_document(
        workflow,
        foreach.over.root,
        stack=controller_stack,
        foreach_nodes=foreach_nodes,
        owner_stack_by_node=owner_stack_by_node,
    )
    try:
        resolved_items = _resolve_local_reference(document, items)
    except ValueError:
        return {}
    result = dict(_inline_local_refs(document, resolved_items))
    if _has_dangling_ref(result):
        # Cut recursions keep their definitions table so downstream walkers
        # can resolve through them instead of meeting a bare `$ref`.
        definitions = _collect_definitions(document)
        if definitions:
            result["$defs"] = definitions
    return deepcopy(result)


def _schema_at_path(
    workflow: Workflow,
    root: str,
    parts: tuple[str, ...],
    stack: ForeachOwnerStack,
    foreach_nodes: Mapping[str, ForeachNode],
    owner_stack_by_node: Mapping[str, ForeachOwnerStack],
) -> Mapping[str, object] | None:
    try:
        schema_document = _schema_document(
            workflow,
            root,
            stack=stack,
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


def normalize_definition_reference(reference: str) -> str:
    """Normalize legacy ``#/definitions/`` refs to ``#/$defs/`` form."""
    if reference.startswith("#/definitions/"):
        return "#/$defs/" + reference.removeprefix("#/definitions/")
    return reference


def _merge_ref_siblings(
    target: Mapping[str, object], node: Mapping[str, object]
) -> dict[str, object]:
    """Merge ``$ref`` siblings over the resolved target (2020-12 conjunction).

    Scalar siblings (``description``, ``title``) override; ``properties`` union
    per key with the sibling winning; ``required`` unions. ``$ref`` itself is
    consumed unless the target chains to another reference.
    """
    merged = dict(target)
    for key, value in node.items():
        if key == "$ref":
            continue
        existing_properties = merged.get("properties")
        if (
            key == "properties"
            and isinstance(value, Mapping)
            and isinstance(existing_properties, Mapping)
        ):
            merged["properties"] = {**existing_properties, **value}
            continue
        existing_required = merged.get("required")
        if (
            key == "required"
            and isinstance(value, list)
            and isinstance(existing_required, list)
        ):
            merged["required"] = [
                *existing_required,
                *[item for item in value if item not in existing_required],
            ]
            continue
        merged[key] = value
    return merged


def _lookup_definition(
    definitions: Mapping[str, object], reference: str
) -> Mapping[str, object] | None:
    """Walk a definition pointer beneath a merged definitions table, leniently.

    Only definition-table pointers resolve here; anything else returns
    ``None`` so callers fail closed.
    """
    normalized = normalize_definition_reference(reference)
    if not normalized.startswith("#/$defs/"):
        return None
    current: object = definitions
    for raw_part in normalized.removeprefix("#/$defs/").split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current if isinstance(current, Mapping) else None


def resolve_schema_reference(
    definitions: Mapping[str, object], node: Mapping[str, object]
) -> Mapping[str, object]:
    """Leniently resolve one node's ``$ref`` chain against a definitions table.

    Unresolvable, external, or cyclic references return ``node`` unchanged so
    schema walkers fail closed. Sibling constraints merge like the strict
    resolver.
    """
    current = node
    seen: set[str] = set()
    while True:
        raw = current.get("$ref")
        if not isinstance(raw, str):
            return current
        reference = normalize_definition_reference(raw)
        if reference in seen or len(seen) >= _MAX_LOCAL_SCHEMA_REFERENCE_DEPTH:
            return node
        seen.add(reference)
        target = _lookup_definition(definitions, reference)
        if target is None:
            return node
        current = _merge_ref_siblings(target, current)


def schema_union_branches(node: Mapping[str, object]) -> list[Mapping[str, object]]:
    """Return object-candidate branches: the node plus anyOf/oneOf/allOf members.

    Composition keywords are a union approximation for path walking: a path is
    readable when some branch declares it. This matches ``Optional[X]``
    (pydantic ``anyOf``) and subclass ``allOf`` shapes; exotic intersections
    may over-accept, which path allowlisting prefers to false rejection.
    """
    branches = [node]
    for key in ("anyOf", "oneOf", "allOf"):
        members = node.get(key)
        if isinstance(members, list):
            branches.extend(member for member in members if isinstance(member, Mapping))
    return branches


def _subtree_references(node: object) -> set[str]:
    """Collect normalized ``$ref`` strings in a subtree (bounded scan)."""
    found: set[str] = set()
    seen: set[int] = set()
    stack: list[object] = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, Mapping):
            if id(current) in seen:
                continue
            seen.add(id(current))
            reference = current.get("$ref")
            if isinstance(reference, str):
                found.add(normalize_definition_reference(reference))
            stack.extend(current.values())
        elif isinstance(current, list):
            if id(current) in seen:
                continue
            seen.add(id(current))
            stack.extend(current)
    return found


def _inline_local_refs(
    root_schema: Mapping[str, object],
    candidate: Mapping[str, object],
) -> Mapping[str, object]:
    """Return ``candidate`` with nested local refs resolved inline.

    :func:`_foreach_item_schema` detaches the resolved item schema from its
    source document, which would strand nested ``$ref`` pointers whose
    ``$defs`` live at the document root. Inlining here resolves the
    acyclic majority (including ``anyOf``/``allOf``/``oneOf`` composition and
    ``$ref`` siblings) so downstream walkers mostly see plain ``properties``.
    Cut recursions keep a normalized dangling ``$ref``; their definitions
    table travels with the item schema (see :func:`_foreach_item_schema`) for
    ref-aware walkers.
    """

    def inline(node: object, active: frozenset[str], depth: int) -> object:
        if depth > _MAX_LOCAL_SCHEMA_REFERENCE_DEPTH:
            return node
        if isinstance(node, list):
            return [inline(item, active, depth + 1) for item in node]
        if not isinstance(node, Mapping):
            return node
        reference = node.get("$ref")
        if isinstance(reference, str):
            lookup = normalize_definition_reference(reference)
            if lookup in active:
                rewritten = dict(node)
                rewritten["$ref"] = lookup
                return rewritten
            try:
                resolved = _resolve_local_reference(root_schema, node)
            except ValueError:
                rewritten = dict(node)
                if lookup != reference:
                    rewritten["$ref"] = lookup
                return rewritten
            target_refs = _subtree_references(resolved)
            if lookup in target_refs or not target_refs.isdisjoint(active):
                # Recursive shape: expanding would re-enter this reference or
                # an ancestor, so keep it dangling and let the attached
                # definitions table serve ref-aware walkers instead.
                rewritten = dict(node)
                rewritten["$ref"] = lookup
                return rewritten
            return inline(resolved, active | {lookup}, depth + 1)
        inlined = dict(node)
        properties = inlined.get("properties")
        if isinstance(properties, Mapping):
            inlined["properties"] = {
                name: inline(sub, active, depth + 1) for name, sub in properties.items()
            }
        items = inlined.get("items")
        if isinstance(items, (Mapping, list)):
            inlined["items"] = inline(items, active, depth + 1)
        additional = inlined.get("additionalProperties")
        if isinstance(additional, (Mapping, list)):
            inlined["additionalProperties"] = inline(additional, active, depth + 1)
        prefix = inlined.get("prefixItems")
        if isinstance(prefix, list):
            inlined["prefixItems"] = inline(prefix, active, depth + 1)
        for key in ("anyOf", "oneOf", "allOf"):
            members = inlined.get(key)
            if isinstance(members, list):
                inlined[key] = [inline(member, active, depth + 1) for member in members]
        return inlined

    inlined = inline(candidate, frozenset(), 0)
    if not isinstance(inlined, Mapping):
        return candidate
    return inlined


def _has_dangling_ref(node: object) -> bool:
    """Return whether any nested mapping still carries a string ``$ref``."""
    seen: set[int] = set()
    stack: list[object] = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, Mapping):
            if id(current) in seen:
                continue
            seen.add(id(current))
            if isinstance(current.get("$ref"), str):
                return True
            stack.extend(current.values())
        elif isinstance(current, list):
            if id(current) in seen:
                continue
            seen.add(id(current))
            stack.extend(current)
    return False


def _collect_definitions(document: Mapping[str, object]) -> dict[str, object]:
    """Merge a document's ``definitions``/``$defs`` tables (``$defs`` wins)."""
    collected: dict[str, object] = {}
    legacy = document.get("definitions")
    if isinstance(legacy, Mapping):
        collected.update(legacy)
    modern = document.get("$defs")
    if isinstance(modern, Mapping):
        collected.update(modern)
    return collected


def _resolve_local_reference(
    root_schema: Mapping[str, object],
    candidate: Mapping[str, object],
) -> Mapping[str, object]:
    """Resolve bounded repository-local refs without becoming a full resolver.

    ``$ref`` siblings merge over the resolved target (JSON Schema 2020-12
    conjunction, bounded to scalar override plus ``properties``/``required``
    union); the merged result keeps resolving when the target chains.
    """
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
        current = _merge_ref_siblings(resolved, current)
    return current
