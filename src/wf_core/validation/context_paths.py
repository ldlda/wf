from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any

from wf_core.analysis.context_scopes import (
    ContextSchema,
    resolve_schema_reference,
    root_context_schema,
    schema_union_branches,
)
from wf_core.analysis.control_regions import ControlRegionAnalysis
from wf_core.context_contracts import RESERVED_CONTEXT_KEYS
from wf_core.models.conditions import (
    BinaryCondition,
    Condition,
    ExistsCondition,
    LiteralOperand,
    NotCondition,
    PathOperand,
    VariadicCondition,
)
from wf_core.models.input_bindings import (
    ArrayExpression,
    InputExpression,
    InputExpressionBinding,
    InputPathBinding,
    LiteralExpression,
    ObjectExpression,
    PathExpression,
)
from wf_core.models.steps import (
    ConditionNode,
    ForeachNode,
    InterruptNode,
    NodeUse,
    SubgraphNode,
)
from wf_core.models.workflow import Workflow
from wf_core.paths import GraphSourcePath
from wf_core.validation.issues import ValidationIssueCode, ValidationReport


def validate_context_paths(
    workflow: Workflow,
    *,
    context_schemas: Mapping[str, ContextSchema],
    report: ValidationReport,
    control_regions: ControlRegionAnalysis | None = None,
) -> None:
    """Validate every ``context.*`` path against its consuming location schema.

    Ordinary input/state validation stays where it is; this pass owns the
    stronger program-location-aware meaning of ``context.*``. A path is valid
    only if every literal segment is a declared object property in the
    consuming node's generated schema. The whole ``context`` object and the
    ``context.foreach`` map remain readable; unknown dynamic keys do not.
    The shared control-region analysis is threaded through so validation runs
    it once; alias ownership never triggers a second traversal.
    """
    nodes_by_index = list(workflow.nodes)
    node_index_by_id = {node.id: idx for idx, node in enumerate(nodes_by_index)}
    _validate_alias_ownership(
        workflow, node_index_by_id, report, control_regions=control_regions
    )
    for idx, node in enumerate(nodes_by_index):
        schema = context_schemas.get(node.id)
        if isinstance(node, NodeUse):
            _validate_step_input_bindings(
                node.input, f"nodes[{idx}].input", node.id, schema, report
            )
        elif isinstance(node, SubgraphNode):
            _validate_step_input_bindings(
                node.input, f"nodes[{idx}].input", node.id, schema, report
            )
        elif isinstance(node, ConditionNode):
            for location, path in _condition_paths(node.check, f"nodes[{idx}].check"):
                _validate_one_context_path(path, location, node.id, schema, report)
        elif isinstance(node, ForeachNode):
            # Context-rooted `over` paths reach this pass; the old
            # input/state-only check stays permissive for them.
            if node.over.root == "context":
                _validate_one_context_path(
                    node.over, f"nodes[{idx}].over", node.id, schema, report
                )
        elif isinstance(node, InterruptNode):
            _validate_step_input_bindings(
                node.request, f"nodes[{idx}].request", node.id, schema, report
            )
    _validate_workflow_output(workflow, report)


def _validate_step_input_bindings(
    bindings: list[Any],
    base: str,
    node_id: str,
    schema: ContextSchema | None,
    report: ValidationReport,
) -> None:
    """Validate context paths in one input/request binding list.

    `base` is the list location such as `nodes[3].input` or
    `nodes[1].request`; each binding contributes `base[i]` and each path
    field contributes a further suffix like `.path` or
    `.expression.items[0].path`.
    """
    for binding_index, binding in enumerate(bindings):
        binding_location = f"{base}[{binding_index}]"
        if isinstance(binding, InputPathBinding):
            if binding.path.root == "context":
                _validate_one_context_path(
                    binding.path, f"{binding_location}.path", node_id, schema, report
                )
        elif isinstance(binding, InputExpressionBinding):
            for location, path in _expression_paths(
                binding.expression, f"{binding_location}.expression"
            ):
                if path.root == "context":
                    _validate_one_context_path(path, location, node_id, schema, report)


def _expression_paths(
    expression: InputExpression,
    location: str,
) -> Iterator[tuple[str, GraphSourcePath]]:
    """Yield ``(model path, graph path)`` for every path leaf in an expression.

    Finite recursion mirrors the input-expression model: paths, arrays, and
    objects. Literals contribute no paths.
    """
    match expression:
        case PathExpression(path=path):
            yield location + ".path", path
        case ArrayExpression(items=items):
            for index, item in enumerate(items):
                yield from _expression_paths(item, f"{location}.items[{index}]")
        case ObjectExpression(fields=fields):
            for name, item in fields.items():
                yield from _expression_paths(item, f"{location}.fields.{name}")
        case LiteralExpression():
            return


def _condition_paths(
    condition: Condition,
    location: str,
) -> Iterator[tuple[str, GraphSourcePath]]:
    """Yield context-candidate paths from a condition tree with model locations."""
    if isinstance(condition, ExistsCondition):
        yield location + ".path", condition.path
        return
    if isinstance(condition, NotCondition):
        yield from _condition_paths(condition.arg, f"{location}.arg")
        return
    if isinstance(condition, VariadicCondition):
        for index, arg in enumerate(condition.args):
            yield from _condition_paths(arg, f"{location}.args[{index}]")
        return
    if isinstance(condition, BinaryCondition):
        yield from _operand_paths(condition.left, f"{location}.left")
        yield from _operand_paths(condition.right, f"{location}.right")
        return


def _operand_paths(
    operand: PathOperand | LiteralOperand, location: str
) -> Iterator[tuple[str, GraphSourcePath]]:
    if isinstance(operand, LiteralOperand):
        return
    yield location + ".path", operand.path


def _validate_one_context_path(
    path: GraphSourcePath,
    location: str,
    node_id: str | None,
    schema: ContextSchema | None,
    report: ValidationReport,
) -> None:
    if path.root != "context":
        return
    if schema is None:
        report.add(
            ValidationIssueCode.INVALID_CONTEXT_PATH,
            location,
            f"invalid context path {str(path)!r} at {node_id or location!r}: "
            "no context schema for this program location",
        )
        return
    failing, available = _failing_segment(schema, path.parts)
    if failing is not None:
        listed = f" (available: {available})" if available else ""
        report.add(
            ValidationIssueCode.INVALID_CONTEXT_PATH,
            location,
            f"invalid context path {str(path)!r} at {node_id or location!r}: "
            f"unknown segment {failing!r}{listed}",
        )


def _failing_segment(
    schema: Mapping[str, Any], parts: tuple[str, ...]
) -> tuple[str | None, str]:
    """Return the first unknown segment plus the keys available there.

    Returns ``(None, "")`` when the path walks declared properties (or
    permissive unconstrained schemas). Dangling ``$ref`` values resolve
    against the nearest enclosing ``$defs`` table (kept by recursive item
    schemas); unresolvable refs fail closed. Composition keywords are a
    union: a path is readable when some branch declares it.
    """
    if not parts:
        return None, ""
    table = schema.get("$defs")
    definitions = table if isinstance(table, Mapping) else {}
    return _walk_schema(schema, parts, definitions)


def _walk_schema(
    node: Any,
    parts: tuple[str, ...],
    definitions: Mapping[str, Any],
) -> tuple[str | None, str]:
    """Walk one schema level: normalize, resolve refs, try union branches."""
    if not parts:
        return None, ""
    if not isinstance(node, Mapping):
        return parts[0], ""
    table = node.get("$defs")
    if isinstance(table, Mapping):
        definitions = table
    if isinstance(node.get("$ref"), str):
        resolved = resolve_schema_reference(definitions, node)
        if resolved is node:
            return parts[0], ""
        return _walk_schema(resolved, parts, definitions)
    failures: list[tuple[str, str]] = []
    for branch in schema_union_branches(node):
        failing, available = _walk_branch(branch, parts, definitions)
        if failing is None:
            return None, ""
        failures.append((failing, available))
    # Prefer the failure that names available keys; single-branch schemas
    # behave exactly as before.
    for failing, available in failures:
        if available:
            return failing, available
    return failures[0]


def _walk_branch(
    branch: Mapping[str, Any],
    parts: tuple[str, ...],
    definitions: Mapping[str, Any],
) -> tuple[str | None, str]:
    """Walk literal parts through one branch's declared properties."""
    if isinstance(branch.get("$ref"), str):
        # A referenced branch resolves first so recursion through definitions
        # tables validates; unresolvable branches simply cannot accept.
        resolved = resolve_schema_reference(definitions, branch)
        if resolved is branch:
            return parts[0], ""
        return _walk_schema(resolved, parts, definitions)
    part = parts[0]
    properties = branch.get("properties")
    if not isinstance(properties, Mapping):
        if branch == {}:
            return None, ""
        if (
            branch.get("type") == "object"
            and branch.get("additionalProperties", True) is not False
        ):
            return None, ""
        return part, ""
    if part not in properties:
        return part, ",".join(sorted(str(key) for key in properties))
    return _walk_schema(properties[part], parts[1:], definitions)


def _validate_workflow_output(workflow: Workflow, report: ValidationReport) -> None:
    schema = root_context_schema()
    for output_index, binding in enumerate(workflow.output):
        if isinstance(binding, InputPathBinding):
            if binding.path.root == "context":
                _validate_one_context_path(
                    binding.path,
                    f"output[{output_index}].path",
                    "workflow_output",
                    schema,
                    report,
                )
        elif isinstance(binding, InputExpressionBinding):
            for location, path in _expression_paths(
                binding.expression, f"output[{output_index}].expression"
            ):
                if path.root == "context":
                    _validate_one_context_path(
                        path, location, "workflow_output", schema, report
                    )


def _validate_alias_ownership(
    workflow: Workflow,
    node_index_by_id: dict[str, int],
    report: ValidationReport,
    *,
    control_regions: ControlRegionAnalysis | None = None,
) -> None:
    """Reject reserved or colliding active foreach aliases.

    Reserved names are every standard context field plus ``foreach``,
    ``loop_item``, and ``loop_index`` (that is, ``RESERVED_CONTEXT_KEYS``).
    Siblings in separate control regions may reuse an alias because they are
    never active together; only aliases active in the same owner stack
    collide. Failures point at the inner foreach's ``as`` field. The shared
    control-region analysis is reused; this helper never traverses alone.
    """
    if control_regions is None:
        from wf_core.analysis.control_regions import analyze_control_regions

        control_regions = analyze_control_regions(workflow)
    analysis = control_regions
    foreach_by_id = {
        node.id: node for node in workflow.nodes if isinstance(node, ForeachNode)
    }
    reported: set[str] = set()
    for stack in analysis.owner_stack_by_node.values():
        seen_aliases: dict[str, str] = {}
        for owner_id in stack:
            foreach = foreach_by_id.get(owner_id)
            if foreach is None:
                continue
            alias = foreach.as_
            idx = node_index_by_id.get(owner_id)
            location = f"nodes[{idx}].as" if idx is not None else f"nodes[{owner_id}]"
            if not alias or alias in RESERVED_CONTEXT_KEYS:
                if owner_id not in reported:
                    reported.add(owner_id)
                    report.add(
                        ValidationIssueCode.FOREACH_CONTEXT_ALIAS_CONFLICT,
                        location,
                        f"foreach alias {alias!r} for node {owner_id!r} "
                        "collides with reserved context keys",
                    )
                continue
            if alias in seen_aliases:
                if owner_id not in reported:
                    reported.add(owner_id)
                    report.add(
                        ValidationIssueCode.FOREACH_CONTEXT_ALIAS_CONFLICT,
                        location,
                        f"foreach alias {alias!r} for node {owner_id!r} "
                        f"collides with active alias from {seen_aliases[alias]!r}",
                    )
                continue
            seen_aliases[alias] = owner_id
