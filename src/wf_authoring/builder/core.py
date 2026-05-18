from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, cast
import warnings
from warnings import deprecated

from wf_authoring.ops.values import runtime_error
from wf_core import (
    ConditionNode,
    Edge,
    ForeachNode,
    InterruptNode,
    NodeUse,
    SchemaRef,
    StateSchema,
    Workflow,
    RunState,
    execute_workflow,
)
from wf_core.errors import WorkflowExecutionError
from wf_core.models.conditions import Condition as CoreCondition
from wf_core.models.conditions import BinaryCondition, ExistsCondition, PathOperand
from wf_core.runtime.ops.merges import ReducerDefinition

from ..dsl import Expr, PathArg, PathExpr, compile_condition
from ..nodes.callables import SyncRegistryHandler
from ..nodes.registry import build_registry
from ..reducers import ReducerCatalog
from ..schemas import SchemaLike, StateSchemaLike, schema_ref_from, state_schema_from
from ..nodes import NodeSpec
from .ids import next_step_id, slug_id
from .mapping import (
    MapArg,
    auto_input_map,
    auto_output_map,
    coerce_path,
    normalize_mapping,
)
from .refs import BranchRef, RouteRef, StepRef, is_node_spec, step_id


def _condition_base(condition: CoreCondition) -> str:
    """Return a small source-derived id base when one path is obvious."""
    if isinstance(condition, ExistsCondition):
        return slug_id(condition.path)
    if isinstance(condition, BinaryCondition) and isinstance(
        condition.left, PathOperand
    ):
        return slug_id(condition.left.path)
    return "condition"


@dataclass(slots=True)
class WorkflowBuilder:
    name: str
    input_schema: SchemaLike
    state_schema: StateSchemaLike
    output_schema: SchemaLike
    start: str | None = None
    reducers: ReducerCatalog | Mapping[str, ReducerDefinition] | None = None
    node_specs: dict[str, NodeSpec[Any, Any]] = field(default_factory=dict)
    nodes: list[Any] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Normalize authoring-friendly schema declarations into core schemas."""
        self.input_schema = schema_ref_from(self.input_schema)
        self.state_schema = state_schema_from(self.state_schema)
        self.output_schema = schema_ref_from(self.output_schema)

    def use(
        self,
        spec: NodeSpec[Any, Any],
        *,
        id: str | None = None,
        in_map: MapArg | None = None,
        out_map: MapArg | None = None,
        desc: str | None = None,
    ) -> NodeUse:
        self.node_specs[spec.name] = spec
        normalized_input_schema = cast(SchemaRef, self.input_schema)
        normalized_state_schema = cast(StateSchema, self.state_schema)
        node = NodeUse(
            id=id or self._next_step_id(slug_id(spec.name)),
            type="node",
            node=spec.name,
            desc=desc or spec.description,
            in_map=(
                auto_input_map(
                    spec,
                    input_schema=normalized_input_schema,
                    state_schema=normalized_state_schema,
                )
                if in_map is None
                else normalize_mapping(in_map)
            ),
            out_map=(
                auto_output_map(spec, state_schema=normalized_state_schema)
                if out_map is None
                else normalize_mapping(out_map)
            ),
        )
        self.nodes.append(node)
        return node

    def use_ref(
        self,
        name: str,
        *,
        id: str | None = None,
        in_map: MapArg | None = None,
        out_map: MapArg | None = None,
        desc: str | None = None,
    ) -> NodeUse:
        """Use an already-named external capability without a local `NodeSpec`.

        `use()` is for callable-backed Python specs that can contribute a local
        node definition and registry handler. `use_ref()` is the matching escape
        hatch for MCP/saved-workflow capability refs that are resolved later by
        the environment runner into node definitions and registry handlers.
        """
        node = NodeUse(
            id=id or self._next_step_id(slug_id(name)),
            type="node",
            node=name,
            desc=desc,
            in_map=normalize_mapping(in_map),
            out_map=normalize_mapping(out_map),
        )
        self.nodes.append(node)
        return node

    def _next_step_id(self, base: str) -> str:
        """Return a stable unused step id based on the requested base name."""
        return next_step_id(base, cast(list[StepRef], self.nodes))

    def set_entry_point(self, step: StepRef) -> None:
        """Set the workflow start node explicitly."""
        self.start = step_id(step)

    def registry(self) -> dict[str, SyncRegistryHandler]:
        """Export handlers for all node specs used by this builder."""
        return build_registry(*self.node_specs.values())

    def reducer_registry(self) -> dict[str, ReducerDefinition]:
        """Export custom reducers attached to this builder.

        The core runtime always falls back to built-in reducers. This method
        returns only the authored additions/overrides so callers can pass the
        same runtime environment that `execute()` uses.
        """
        if self.reducers is None:
            return {}
        if isinstance(self.reducers, ReducerCatalog):
            return dict(self.reducers.definitions)
        return dict(self.reducers)

    def execute(self, workflow_input: dict[str, Any]) -> RunState:
        """Compile and execute this workflow with its used node registry.

        This is intended for tests, examples, and local authoring loops. Production
        callers that need custom registries, persistence, or resume behavior should
        call wf_core execution functions directly.
        """
        return execute_workflow(
            self.compile(),
            workflow_input,
            self.registry(),
            reducers=self.reducer_registry(),
        )

    def condition(
        self, *, id: str | None = None, check: CoreCondition | Expr
    ) -> ConditionNode:
        compiled = compile_condition(check)
        node = ConditionNode(
            id=id or self._next_step_id(_condition_base(compiled)),
            type="condition",
            check=compiled,
        )
        self.nodes.append(node)
        return node

    def foreach(
        self,
        *,
        id: str | None = None,
        over: PathArg,
        as_: str,
        mode: Literal["serial", "parallel"] = "serial",
        on_item_error: Literal["fail", "collect", "skip"] = "fail",
    ) -> ForeachNode:
        node = ForeachNode.model_validate(
            {
                "id": id or self._next_step_id(f"foreach_{slug_id(as_)}"),
                "type": "foreach",
                "over": coerce_path(over),
                "as": as_,
                "mode": mode,
                "on_item_error": on_item_error,
            }
        )
        self.nodes.append(node)
        return node

    def interrupt(
        self,
        *,
        id: str | None = None,
        kind: str,
        request_map: MapArg | None = None,
        out_map: MapArg | None = None,
        outcomes: list[str] | None = None,
    ) -> InterruptNode:
        node = InterruptNode(
            id=id or self._next_step_id(f"interrupt_{slug_id(kind)}"),
            type="interrupt",
            kind=kind,
            request_map=normalize_mapping(request_map),
            out_map=normalize_mapping(out_map),
            outcomes=outcomes or ["submitted"],
        )
        self.nodes.append(node)
        return node

    def connect(
        self,
        from_: BranchRef,
        outcome: str,
        to: BranchRef,
    ) -> tuple[StepRef, StepRef]:
        """Connect one outcome, auto-using NodeSpec endpoints as fresh node uses."""
        source = self.use(from_) if is_node_spec(from_) else from_
        target = self.use(to) if is_node_spec(to) else to
        self.edges.append(
            Edge.model_validate(
                {
                    "from": step_id(cast(StepRef, source)),
                    "outcome": outcome,
                    "to": step_id(cast(StepRef, target)),
                }
            )
        )
        return cast(StepRef, source), cast(StepRef, target)

    def branch(
        self,
        from_: BranchRef,
        branches: Mapping[str, BranchRef],
    ) -> dict[str, StepRef]:
        """Connect multiple outcomes from one branch source.

        Passing a NodeSpec creates a node use with auto-mapping and an auto id.
        Passing an existing step or id only wires edges. Empty branch maps are
        allowed but warn because they usually indicate an unfinished router.
        The returned mapping is keyed by branch outcome, not generated target id.
        """
        if not branches:
            warnings.warn(
                "WorkflowBuilder.branch called with no branches",
                UserWarning,
                stacklevel=2,
            )
            return {}

        source = self.use(from_) if is_node_spec(from_) else from_
        resolved_targets: dict[str, StepRef] = {}
        for outcome, target in branches.items():
            resolved = self.use(target) if is_node_spec(target) else target
            self.connect(cast(StepRef, source), outcome, cast(StepRef, resolved))
            resolved_targets[outcome] = cast(StepRef, resolved)
        return resolved_targets

    def match(
        self,
        value: PathExpr,
        cases: Mapping[object, BranchRef],
        *,
        id: str | None = None,
        default: BranchRef = runtime_error,
    ) -> RouteRef:
        """Match one graph value against ordered equality cases."""
        resolved_targets: dict[object, StepRef] = {}
        conditions: list[ConditionNode] = []
        default_target = self.use(default) if is_node_spec(default) else default
        previous_condition: ConditionNode | None = None
        condition_base = id or slug_id(value.path)
        for case_value, target in cases.items():
            condition = self.condition(
                id=self._next_step_id(condition_base),
                check=value.eq(case_value),
            )
            conditions.append(condition)
            resolved = self.use(target) if is_node_spec(target) else target
            if previous_condition is not None:
                self.connect(previous_condition, "false", condition)
            self.connect(condition, "true", cast(StepRef, resolved))
            previous_condition = condition
            resolved_targets[case_value] = cast(StepRef, resolved)
        if previous_condition is None:
            raise ValueError("WorkflowBuilder.match requires at least one case")
        self.connect(previous_condition, "false", cast(StepRef, default_target))
        resolved_targets["default"] = cast(StepRef, default_target)
        return RouteRef(
            entry=conditions[0],
            conditions=tuple(conditions),
            targets=resolved_targets,
        )

    def when(
        self,
        condition: Expr,
        *,
        then: BranchRef,
        otherwise: BranchRef = runtime_error,
        id: str | None = None,
    ) -> RouteRef:
        """Route one boolean condition through true and false targets."""
        condition_node = self.condition(id=id, check=condition)
        resolved_then = self.use(then) if is_node_spec(then) else then
        resolved_otherwise = (
            self.use(otherwise) if is_node_spec(otherwise) else otherwise
        )
        self.connect(condition_node, "true", cast(StepRef, resolved_then))
        self.connect(condition_node, "false", cast(StepRef, resolved_otherwise))
        return RouteRef(
            entry=condition_node,
            conditions=(condition_node,),
            targets={
                True: cast(StepRef, resolved_then),
                False: cast(StepRef, resolved_otherwise),
            },
        )

    def choose(
        self,
        *clauses: tuple[Expr, BranchRef],
        default: BranchRef = runtime_error,
        id: str | None = None,
    ) -> RouteRef:
        """Route to the first target whose ordered condition is true."""
        if not clauses:
            raise ValueError("WorkflowBuilder.choose requires at least one clause")

        conditions: list[ConditionNode] = []
        resolved_targets: dict[object, StepRef] = {}
        previous_condition: ConditionNode | None = None
        condition_base = id or _condition_base(compile_condition(clauses[0][0]))
        for index, (condition_expr, target) in enumerate(clauses):
            condition = self.condition(
                id=self._next_step_id(condition_base),
                check=condition_expr,
            )
            conditions.append(condition)
            resolved = self.use(target) if is_node_spec(target) else target
            if previous_condition is not None:
                self.connect(previous_condition, "false", condition)
            self.connect(condition, "true", cast(StepRef, resolved))
            previous_condition = condition
            resolved_targets[index] = cast(StepRef, resolved)
        default_target = self.use(default) if is_node_spec(default) else default
        self.connect(cast(ConditionNode, previous_condition), "false", cast(StepRef, default_target))
        resolved_targets["default"] = cast(StepRef, default_target)
        return RouteRef(
            entry=conditions[0],
            conditions=tuple(conditions),
            targets=resolved_targets,
        )

    @deprecated("use match(...) or when(...) instead")
    def route(
        self,
        value: PathExpr | Expr,
        cases: Mapping[object, BranchRef],
        *,
        id: str | None = None,
        default: BranchRef = runtime_error,
    ) -> RouteRef:
        """Deprecated compatibility shim for the old overloaded route API."""
        warnings.warn(
            "WorkflowBuilder.route is deprecated; use match(...) or when(...)",
            DeprecationWarning,
            stacklevel=2,
        )
        if isinstance(value, Expr):
            invalid_cases = [case for case in cases if not isinstance(case, bool)]
            if invalid_cases:
                raise ValueError("condition route cases must be boolean True/False keys")
            if not cases:
                raise ValueError("WorkflowBuilder.route requires at least one case")
            return self.when(
                value,
                then=cases.get(True, default),
                otherwise=cases.get(False, default),
                id=id,
            )
        return self.match(value, cases, id=id, default=default)

    def compile(self) -> Workflow:
        if self.start is None:
            raise WorkflowExecutionError(
                "workflow builder requires an explicit start; call set_entry_point(...) "
                "or pass start=..."
            )
        node_defs = [spec.to_node_def() for spec in self.node_specs.values()]
        return Workflow(
            name=self.name,
            input_schema=cast(SchemaRef, self.input_schema),
            state_schema=cast(StateSchema, self.state_schema),
            output_schema=cast(SchemaRef, self.output_schema),
            node_defs=node_defs,
            start=self.start,
            nodes=self.nodes,
            edges=self.edges,
        )
