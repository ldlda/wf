from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, overload, cast
import warnings
from warnings import deprecated

from wf_authoring.ops.values import runtime_error
from wf_core import (
    ConditionNode,
    Edge,
    ForeachConcurrentPolicy,
    ForeachItemErrorPolicy,
    ForeachNode,
    InterruptNode,
    NodeUse,
    SchemaRef,
    StateSchema,
    SubgraphNode,
    Workflow,
    RunState,
    execute_workflow,
)
from wf_core.errors import WorkflowExecutionError
from wf_core.models.conditions import Condition as CoreCondition
from wf_core.models.conditions import BinaryCondition, ExistsCondition, PathOperand
from wf_core.models.steps import (
    InputBinding,
    InputPathBinding,
    InputValueBinding,
    OutputBinding,
    Step,
)
from wf_core.paths import GraphSourcePath, LocalPath, StatePath
from wf_core.runtime.ops.merges import ReducerDefinition

from ..dsl import Expr, GraphPath, PathArg, PathExpr, compile_condition
from ..nodes.callables import SyncRegistryHandler
from ..nodes.registry import build_registry
from ..reducers import ReducerCatalog
from ..schemas import SchemaLike, StateSchemaLike, schema_ref_from, state_schema_from
from ..subgraph import subgraph_ref
from ..nodes import NodeSpec
from .ids import next_step_id, slug_id
from .mapping import (
    InputBindingArg,
    MapArg,
    OutputBindingArg,
    auto_input_map,
    auto_output_map,
    coerce_path,
    normalize_input_bindings,
    normalize_input_mapping,
    normalize_input_values,
    normalize_output_bindings,
    normalize_output_mapping,
)
from .refs import (
    BranchRef,
    BranchResult,
    DecisionResult,
    HandleResult,
    StepRef,
    step_id,
)


def _condition_base(condition: CoreCondition) -> str:
    """Return a small source-derived id base when one path is obvious."""
    if isinstance(condition, ExistsCondition):
        return slug_id(str(condition.path))
    if isinstance(condition, BinaryCondition) and isinstance(
        condition.left, PathOperand
    ):
        return slug_id(str(condition.left.path))
    return "condition"


def _canonical_input_bindings(
    in_map: Mapping[GraphSourcePath, LocalPath],
    input_values: Mapping[LocalPath, Any],
) -> list[InputBinding]:
    """Convert typed authoring maps into canonical core input bindings."""
    value_bindings = [
        InputValueBinding(target=target, value=value)
        for target, value in input_values.items()
    ]
    path_bindings = [
        InputPathBinding(
            target=target,
            path=path,
        )
        for path, target in in_map.items()
    ]
    return [*value_bindings, *path_bindings]


def _canonical_output_bindings(
    out_map: Mapping[LocalPath, StatePath],
) -> list[OutputBinding]:
    """Convert typed authoring maps into canonical core output bindings."""
    return [
        OutputBinding(source=source, target=target)
        for source, target in out_map.items()
    ]


def _reject_mixed_binding_styles(
    *,
    input: object | None,
    output: object | None,
    in_map: object | None,
    input_values: object | None,
    out_map: object | None,
) -> None:
    """Keep canonical binding lists and deprecated map sugar from mixing."""
    if input is not None and (in_map is not None or input_values is not None):
        raise TypeError(
            "cannot mix canonical input with deprecated in_map/input_values"
        )
    if output is not None and out_map is not None:
        raise TypeError("cannot mix canonical output with deprecated out_map")


def _warn_deprecated_binding_sugar(
    *,
    in_map: object | None,
    input_values: object | None,
    out_map: object | None,
) -> None:
    """Warn when callers explicitly use map sugar instead of canonical bindings."""
    used = [
        name
        for name, value in (
            ("in_map", in_map),
            ("input_values", input_values),
            ("out_map", out_map),
        )
        if value is not None
    ]
    if not used:
        return
    warnings.warn(
        f"{', '.join(used)} are deprecated WorkflowBuilder sugar; use canonical "
        "input/output binding lists instead",
        DeprecationWarning,
        stacklevel=3,
    )


def _normalize_foreach_item_error(
    item_error: ForeachItemErrorPolicy | Mapping[str, object] | str | None,
) -> ForeachItemErrorPolicy | dict[str, object] | str | None:
    """Coerce authoring path helpers inside the canonical item-error policy."""
    if item_error is None or isinstance(item_error, ForeachItemErrorPolicy | str):
        return item_error

    normalized = dict(item_error)
    collect_to = normalized.get("collect_to")
    if isinstance(collect_to, PathExpr):
        collect_to = collect_to.path
    if isinstance(collect_to, GraphPath):
        collect_to = collect_to.path
    if isinstance(collect_to, GraphSourcePath):
        if collect_to.root != "state":
            raise ValueError("foreach item_error.collect_to must be a state path")
        collect_to = StatePath(collect_to.parts)
    if collect_to is not None:
        normalized["collect_to"] = collect_to
    return normalized


@dataclass(slots=True)
class WorkflowBuilder:
    name: str
    input_schema: SchemaLike
    state_schema: StateSchemaLike
    output_schema: SchemaLike
    start: str | None = None
    reducers: ReducerCatalog | Mapping[str, ReducerDefinition] | None = None
    node_specs: dict[str, NodeSpec[Any, Any]] = field(default_factory=dict)
    nodes: list[Step] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Normalize authoring-friendly schema declarations into core schemas."""
        self.input_schema = schema_ref_from(self.input_schema)
        self.state_schema = state_schema_from(self.state_schema)
        self.output_schema = schema_ref_from(self.output_schema)

    @overload
    def use(
        self,
        spec: NodeSpec[Any, Any],
        *,
        id: str | None = None,
        input: Sequence[InputBindingArg] | None = None,
        output: Sequence[OutputBindingArg] | None = None,
        desc: str | None = None,
    ) -> NodeUse: ...

    @overload
    @deprecated("use input/output canonical binding lists instead")
    def use(
        self,
        spec: NodeSpec[Any, Any],
        *,
        id: str | None = None,
        in_map: MapArg | None = None,
        input_values: Mapping[Any, Any] | None = None,
        out_map: MapArg | None = None,
        desc: str | None = None,
    ) -> NodeUse: ...

    def use(
        self,
        spec: NodeSpec[Any, Any],
        *,
        id: str | None = None,
        input: Sequence[InputBindingArg] | None = None,
        output: Sequence[OutputBindingArg] | None = None,
        in_map: MapArg | None = None,
        input_values: Mapping[Any, Any] | None = None,
        out_map: MapArg | None = None,
        desc: str | None = None,
    ) -> NodeUse:
        _reject_mixed_binding_styles(
            input=input,
            output=output,
            in_map=in_map,
            input_values=input_values,
            out_map=out_map,
        )
        _warn_deprecated_binding_sugar(
            in_map=in_map,
            input_values=input_values,
            out_map=out_map,
        )
        self.node_specs[spec.name] = spec
        normalized_input_schema = cast(SchemaRef, self.input_schema)
        normalized_state_schema = cast(StateSchema, self.state_schema)
        if input is not None:
            node_input = normalize_input_bindings(input)
        else:
            raw_in_map = (
                auto_input_map(
                    spec,
                    input_schema=normalized_input_schema,
                    state_schema=normalized_state_schema,
                )
                if in_map is None
                else in_map
            )
            node_input = _canonical_input_bindings(
                normalize_input_mapping(raw_in_map),
                normalize_input_values(input_values),
            )
        if output is not None:
            node_output = normalize_output_bindings(output)
        else:
            raw_out_map = (
                auto_output_map(spec, state_schema=normalized_state_schema)
                if out_map is None
                else out_map
            )
            node_output = _canonical_output_bindings(
                normalize_output_mapping(raw_out_map)
            )
        node = NodeUse(
            id=id or self._next_step_id(slug_id(spec.name)),
            type="node",
            node=spec.name,
            desc=desc or spec.description,
            input=node_input,
            output=node_output,
        )
        self.nodes.append(node)
        return node

    @overload
    def use_ref(
        self,
        name: str,
        *,
        id: str | None = None,
        input: Sequence[InputBindingArg] | None = None,
        output: Sequence[OutputBindingArg] | None = None,
        desc: str | None = None,
    ) -> NodeUse: ...

    @overload
    @deprecated("use input/output canonical binding lists instead")
    def use_ref(
        self,
        name: str,
        *,
        id: str | None = None,
        in_map: MapArg | None = None,
        input_values: Mapping[Any, Any] | None = None,
        out_map: MapArg | None = None,
        desc: str | None = None,
    ) -> NodeUse: ...

    def use_ref(
        self,
        name: str,
        *,
        id: str | None = None,
        input: Sequence[InputBindingArg] | None = None,
        output: Sequence[OutputBindingArg] | None = None,
        in_map: MapArg | None = None,
        input_values: Mapping[Any, Any] | None = None,
        out_map: MapArg | None = None,
        desc: str | None = None,
    ) -> NodeUse:
        """Use an already-named external capability without a local `NodeSpec`.

        `use()` is for callable-backed Python specs that can contribute a local
        node definition and registry handler. `use_ref()` is the matching escape
        hatch for MCP/saved-workflow capability refs that are resolved later by
        the environment runner into node definitions and registry handlers.
        """
        _reject_mixed_binding_styles(
            input=input,
            output=output,
            in_map=in_map,
            input_values=input_values,
            out_map=out_map,
        )
        _warn_deprecated_binding_sugar(
            in_map=in_map,
            input_values=input_values,
            out_map=out_map,
        )
        node_input = (
            normalize_input_bindings(input)
            if input is not None
            else _canonical_input_bindings(
                normalize_input_mapping(in_map),
                normalize_input_values(input_values),
            )
        )
        node_output = (
            normalize_output_bindings(output)
            if output is not None
            else _canonical_output_bindings(normalize_output_mapping(out_map))
        )
        node = NodeUse(
            id=id or self._next_step_id(slug_id(name)),
            type="node",
            node=name,
            desc=desc,
            input=node_input,
            output=node_output,
        )
        self.nodes.append(node)
        return node

    def subgraph(
        self,
        *,
        workflow: Workflow,
        id: str | None = None,
        input: Sequence[InputBindingArg] | None = None,
        output: Sequence[OutputBindingArg] | None = None,
        workflow_ref: str | None = None,
        desc: str | None = None,
    ) -> SubgraphNode:
        """Add a native subgraph boundary using a compiled child workflow contract.

        This only authors the graph boundary. Runtime execution still raises
        until wf_core grows child workflow scope/frame execution.
        """
        node = subgraph_ref(
            id=id or self._next_step_id(slug_id(workflow_ref or workflow.name)),
            workflow=workflow,
            input=normalize_input_bindings(input),
            output=normalize_output_bindings(output),
            workflow_ref=workflow_ref,
            desc=desc,
        )
        self.nodes.append(node)
        return node

    def _next_step_id(self, base: str) -> str:
        """Return a stable unused step id based on the requested base name."""
        return next_step_id(base, self.nodes)

    def _resolve_branch_ref(self, ref: BranchRef) -> StepRef:
        """Resolve a possibly callable-backed branch ref into one step ref."""
        if isinstance(ref, NodeSpec):
            return self.use(ref)
        return ref

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

    @overload
    def foreach(
        self,
        *,
        id: str | None = None,
        over: PathArg,
        as_: str,
        mode: Literal["serial", "concurrent"] = "serial",
        item_error: ForeachItemErrorPolicy | Mapping[str, object] | str | None = None,
        concurrent: ForeachConcurrentPolicy | Mapping[str, object] | None = None,
    ) -> ForeachNode: ...

    @overload
    @deprecated("use item_error canonical policy instead")
    def foreach(
        self,
        *,
        id: str | None = None,
        over: PathArg,
        as_: str,
        mode: Literal["serial", "concurrent"] = "serial",
        on_item_error: Literal["fail", "collect", "skip"] = "fail",
        concurrent: ForeachConcurrentPolicy | Mapping[str, object] | None = None,
    ) -> ForeachNode: ...

    def foreach(
        self,
        *,
        id: str | None = None,
        over: PathArg,
        as_: str,
        mode: Literal["serial", "concurrent"] = "serial",
        item_error: ForeachItemErrorPolicy | Mapping[str, object] | str | None = None,
        on_item_error: Literal["fail", "collect", "skip"] = "fail",
        concurrent: ForeachConcurrentPolicy | Mapping[str, object] | None = None,
    ) -> ForeachNode:
        """Add a foreach step.

        Concurrent mode is supported by the runtime with deterministic barrier
        commits, item error policies, and async item-node batching. See ADR 0002
        for the exact merge and interrupt semantics. Prefer the canonical
        `item_error` policy object/mapping; `on_item_error` is compatibility
        shorthand for older callers.
        """
        if item_error is not None and on_item_error != "fail":
            raise TypeError("cannot mix item_error with deprecated on_item_error")
        if item_error is None and on_item_error != "fail":
            warnings.warn(
                "on_item_error is deprecated WorkflowBuilder foreach sugar; "
                "use item_error={'action': ...} instead",
                DeprecationWarning,
                stacklevel=2,
            )
        node = ForeachNode.model_validate(
            {
                "id": id or self._next_step_id(f"foreach_{slug_id(as_)}"),
                "type": "foreach",
                "over": coerce_path(over),
                "as": as_,
                "mode": mode,
                "item_error": _normalize_foreach_item_error(item_error)
                if item_error is not None
                else {"action": on_item_error},
                "concurrent": concurrent,
            }
        )
        self.nodes.append(node)
        return node

    @overload
    def interrupt(
        self,
        *,
        id: str | None = None,
        kind: str,
        request: Sequence[InputBindingArg] | None = None,
        resume: Sequence[OutputBindingArg] | None = None,
        outcomes: list[str] | None = None,
    ) -> InterruptNode: ...

    @overload
    @deprecated("use request/resume canonical binding lists instead")
    def interrupt(
        self,
        *,
        id: str | None = None,
        kind: str,
        request_map: MapArg | None = None,
        out_map: MapArg | None = None,
        outcomes: list[str] | None = None,
    ) -> InterruptNode: ...

    def interrupt(
        self,
        *,
        id: str | None = None,
        kind: str,
        request: Sequence[InputBindingArg] | None = None,
        resume: Sequence[OutputBindingArg] | None = None,
        request_map: MapArg | None = None,
        out_map: MapArg | None = None,
        outcomes: list[str] | None = None,
    ) -> InterruptNode:
        if request is not None and request_map is not None:
            raise TypeError("cannot mix canonical request with deprecated request_map")
        if resume is not None and out_map is not None:
            raise TypeError("cannot mix canonical resume with deprecated out_map")
        if request_map is not None or out_map is not None:
            warnings.warn(
                "request_map/out_map are deprecated interrupt sugar; use canonical "
                "request/resume binding lists instead",
                DeprecationWarning,
                stacklevel=2,
            )
        request_bindings = (
            normalize_input_bindings(request)
            if request is not None
            else _canonical_input_bindings(
                normalize_input_mapping(request_map),
                {},
            )
        )
        resume_bindings = (
            normalize_output_bindings(resume)
            if resume is not None
            else _canonical_output_bindings(normalize_output_mapping(out_map))
        )
        node = InterruptNode(
            id=id or self._next_step_id(f"interrupt_{slug_id(kind)}"),
            type="interrupt",
            kind=kind,
            request=request_bindings,
            resume=resume_bindings,
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
        source = self._resolve_branch_ref(from_)
        target = self._resolve_branch_ref(to)
        self.edges.append(
            Edge.model_validate(
                {
                    "from": step_id(source),
                    "outcome": outcome,
                    "to": step_id(target),
                }
            )
        )
        return source, target

    def branch(
        self,
        from_: BranchRef,
        branches: Mapping[str, BranchRef],
    ) -> BranchResult:
        """Connect multiple outcomes from one branch source.

        Passing a NodeSpec creates a node use with auto-mapping and an auto id.
        Passing an existing step or id only wires edges.
        The returned mapping is keyed by branch outcome, not generated target id.
        """
        if not branches:
            raise ValueError("WorkflowBuilder.branch requires at least one branch")

        source = self._resolve_branch_ref(from_)
        resolved_targets: dict[str, StepRef] = {}
        for outcome, target in branches.items():
            resolved = self._resolve_branch_ref(target)
            self.connect(source, outcome, resolved)
            resolved_targets[outcome] = resolved
        return BranchResult(source=source, targets=resolved_targets)

    def handle(
        self,
        *branches: tuple[BranchRef, str],
        to: BranchRef,
    ) -> HandleResult:
        """Connect several source outcomes to one shared target."""
        if not branches:
            raise ValueError("WorkflowBuilder.handle requires at least one branch")
        resolved_branches: list[tuple[StepRef, str]] = []
        target = self._resolve_branch_ref(to)
        for branch, outcome in branches:
            resolved = self._resolve_branch_ref(branch)
            self.connect(resolved, outcome, target)
            resolved_branches.append((resolved, outcome))
        return HandleResult(
            target=target,
            branches=tuple(resolved_branches),
        )

    def match(
        self,
        value: PathExpr,
        cases: Mapping[object, BranchRef],
        *,
        id: str | None = None,
        default: BranchRef = runtime_error,
    ) -> DecisionResult:
        """Match one graph value against ordered equality cases.

        DecisionResult.targets is keyed by case value, not generated target id.
        The default case is always available under the "default" key. Case
        values must be hashable and are compared using equality against the
        graph value at runtime, so they should be primitives or tuples of
        primitives for predictable behavior.
        """
        if not cases:
            raise ValueError("WorkflowBuilder.match requires at least one case")
        resolved_targets: dict[object, StepRef] = {}
        conditions: list[ConditionNode] = []
        default_target = self._resolve_branch_ref(default)
        previous_condition: ConditionNode | None = None
        condition_base = id or slug_id(str(value.path))
        for case_value, target in cases.items():
            condition = self.condition(
                id=self._next_step_id(condition_base),
                check=value.eq(case_value),
            )
            conditions.append(condition)
            resolved = self._resolve_branch_ref(target)
            if previous_condition is not None:
                self.connect(previous_condition, "false", condition)
            self.connect(condition, "true", resolved)
            previous_condition = condition
            resolved_targets[case_value] = resolved
        assert previous_condition is not None  # guarded by cases check above
        self.connect(previous_condition, "false", default_target)
        resolved_targets["default"] = default_target
        return DecisionResult(
            entry=conditions[0],
            conditions=tuple(conditions),
            targets=resolved_targets,
        )

    def when(
        self,
        condition: CoreCondition | Expr,
        *,
        then: BranchRef,
        otherwise: BranchRef = runtime_error,
        id: str | None = None,
    ) -> DecisionResult:
        """Route one boolean condition through true and false targets."""
        condition_node = self.condition(id=id, check=condition)
        resolved_then = self._resolve_branch_ref(then)
        resolved_otherwise = self._resolve_branch_ref(otherwise)
        self.connect(condition_node, "true", resolved_then)
        self.connect(condition_node, "false", resolved_otherwise)
        return DecisionResult(
            entry=condition_node,
            conditions=(condition_node,),
            targets={
                True: resolved_then,
                False: resolved_otherwise,
            },
        )

    def choose(
        self,
        *clauses: tuple[CoreCondition | Expr, BranchRef],
        default: BranchRef = runtime_error,
        id: str | None = None,
    ) -> DecisionResult:
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
            resolved = self._resolve_branch_ref(target)
            if previous_condition is not None:
                self.connect(previous_condition, "false", condition)
            self.connect(condition, "true", resolved)
            previous_condition = condition
            resolved_targets[index] = resolved
        default_target = self._resolve_branch_ref(default)
        assert previous_condition is not None  # guarded by clauses check above
        self.connect(previous_condition, "false", default_target)
        resolved_targets["default"] = default_target
        return DecisionResult(
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
    ) -> DecisionResult:
        """Deprecated compatibility shim for the old overloaded route API."""
        warnings.warn(
            "WorkflowBuilder.route is deprecated; use match(...) or when(...)",
            DeprecationWarning,
            stacklevel=2,
        )
        if isinstance(value, Expr):
            invalid_cases = any(not isinstance(case, bool) for case in cases)
            if invalid_cases:
                raise ValueError(
                    "condition route cases must be boolean True/False keys"
                )
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
                "workflow builder requires an explicit start; "
                "call set_entry_point(...) or pass start=..."
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
