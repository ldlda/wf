from __future__ import annotations

from inspect import Parameter, iscoroutinefunction, signature
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import (
    Any,
    Generic,
    Literal,
    Protocol,
    TypeVar,
    cast,
    get_args,
    get_origin,
    get_type_hints,
    overload,
)

from pydantic import BaseModel

from wf_core import NodeDef, RuntimeContext, SchemaRef

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class ContextNodeCallable(Protocol[InputT, OutputT]):
    def __call__(
        self,
        payload: InputT,
        /,
        ctx: RuntimeContext,
    ) -> "NodeReturn[OutputT] | OutputT": ...


class PlainNodeCallable(Protocol[InputT, OutputT]):
    def __call__(self, payload: InputT, /) -> "NodeReturn[OutputT] | OutputT": ...


NodeCallable = ContextNodeCallable[InputT, OutputT] | PlainNodeCallable[
    InputT, OutputT
]


class AsyncContextNodeCallable(Protocol[InputT, OutputT]):
    def __call__(
        self,
        payload: InputT,
        /,
        ctx: RuntimeContext,
    ) -> Awaitable["NodeReturn[OutputT] | OutputT"]: ...


class AsyncPlainNodeCallable(Protocol[InputT, OutputT]):
    def __call__(
        self,
        payload: InputT,
        /,
    ) -> Awaitable["NodeReturn[OutputT] | OutputT"]: ...


AsyncNodeCallable = AsyncContextNodeCallable[
    InputT, OutputT
] | AsyncPlainNodeCallable[InputT, OutputT]

SyncRegistryHandler = Callable[[dict[str, Any], RuntimeContext], dict[str, Any]]
AsyncRegistryHandler = Callable[
    [dict[str, Any], RuntimeContext], Awaitable[dict[str, Any]]
]


def _schema_ref_for(model_type: type[BaseModel]) -> SchemaRef:
    return SchemaRef.model_validate(model_type.model_json_schema())


@dataclass(slots=True)
class NodeReturn(Generic[OutputT]):
    outcome: str
    output: OutputT


def _default_outcome(spec: "NodeSpec[Any, Any]") -> str:
    return spec.outcomes[0]


def _coerce_registry_result(
    *,
    node_name: str,
    output_model: type[BaseModel],
    default_outcome: str,
    raw: NodeReturn[BaseModel] | BaseModel,
) -> dict[str, Any]:
    if isinstance(raw, NodeReturn):
        if not isinstance(raw.output, output_model):
            raise TypeError(
                f"node {node_name!r} returned NodeReturn with unsupported output "
                f"{type(raw.output)!r}"
            )
        return {
            "outcome": raw.outcome,
            "output": raw.output.model_dump(),
        }
    if isinstance(raw, output_model):
        return {"outcome": default_outcome, "output": raw.model_dump()}
    raise TypeError(f"node {node_name!r} returned unsupported value {type(raw)!r}")


def _is_basemodel_subclass(value: object) -> bool:
    return isinstance(value, type) and issubclass(value, BaseModel)


def _infer_models(
    fn: Callable[..., object],
) -> tuple[type[BaseModel], type[BaseModel]]:
    hints = get_type_hints(fn, include_extras=True)
    params = list(signature(fn).parameters.values())
    if len(params) not in {1, 2}:
        raise TypeError("node function must accept (payload) or (payload, ctx)")

    payload_param = params[0]

    if payload_param.kind not in (
        Parameter.POSITIONAL_ONLY,
        Parameter.POSITIONAL_OR_KEYWORD,
    ):
        raise TypeError("node payload parameter must be positional")

    input_model = hints.get(payload_param.name)
    if not _is_basemodel_subclass(input_model):
        raise TypeError("node payload annotation must be a pydantic BaseModel subclass")

    if len(params) == 2:
        ctx_param = params[1]
        if ctx_param.kind not in (
            Parameter.POSITIONAL_ONLY,
            Parameter.POSITIONAL_OR_KEYWORD,
        ):
            raise TypeError("node context parameter must be positional")
        ctx_type = hints.get(ctx_param.name)
        if ctx_type is not RuntimeContext:
            raise TypeError("node context annotation must be wf_core.RuntimeContext")

    return_type = hints.get("return")
    if return_type is None:
        raise TypeError("node function must declare a return annotation")

    if _is_basemodel_subclass(return_type):
        return cast(type[BaseModel], input_model), cast(type[BaseModel], return_type)

    origin = get_origin(return_type)
    if origin is NodeReturn:
        args = get_args(return_type)
        if len(args) != 1 or not _is_basemodel_subclass(args[0]):
            raise TypeError(
                "NodeReturn return annotation must wrap a BaseModel subclass"
            )
        return cast(type[BaseModel], input_model), cast(type[BaseModel], args[0])

    raise TypeError(
        "node return annotation must be a BaseModel subclass or NodeReturn[BaseModel]"
    )


def _accepts_context(fn: Callable[..., object]) -> bool:
    return len(signature(fn).parameters) >= 2


@dataclass(slots=True)
class NodeSpec(Generic[InputT, OutputT]):
    name: str
    input_model: type[InputT]
    output_model: type[OutputT]
    outcomes: tuple[str, ...]
    fn: NodeCallable[InputT, OutputT] | AsyncNodeCallable[InputT, OutputT]
    description: str | None = None
    is_async: bool = False
    accepts_context: bool = True

    def __call__(
        self,
        payload: InputT,
        ctx: RuntimeContext | None = None,
    ) -> NodeReturn[OutputT] | OutputT | Awaitable[NodeReturn[OutputT] | OutputT]:
        if self.accepts_context:
            if ctx is None:
                raise TypeError(f"node {self.name!r} requires RuntimeContext")
            return cast(ContextNodeCallable[InputT, OutputT], self.fn)(payload, ctx)
        return cast(PlainNodeCallable[InputT, OutputT], self.fn)(payload)

    def to_node_def(self) -> NodeDef:
        return NodeDef(
            name=self.name,
            input_schema=_schema_ref_for(self.input_model),
            output_schema=_schema_ref_for(self.output_model),
            outcomes=list(self.outcomes),
        )

    def to_registry_handler(self) -> SyncRegistryHandler:
        if self.is_async:
            raise TypeError(
                f"node {self.name!r} is async and cannot be exported to the sync registry"
            )

        def handler(payload: dict[str, Any], ctx: RuntimeContext) -> dict[str, Any]:
            parsed = self.input_model.model_validate(payload)
            raw = self(parsed, ctx)
            return _coerce_registry_result(
                node_name=self.name,
                output_model=self.output_model,
                default_outcome=_default_outcome(self),
                raw=cast(NodeReturn[BaseModel] | BaseModel, raw),
            )

        return handler

    def to_async_registry_handler(self) -> AsyncRegistryHandler:
        async def handler(
            payload: dict[str, Any],
            ctx: RuntimeContext,
        ) -> dict[str, Any]:
            parsed = self.input_model.model_validate(payload)
            raw_result = self(parsed, ctx)
            if self.is_async:
                raw = await cast(
                    Awaitable[NodeReturn[OutputT] | OutputT],
                    raw_result,
                )
            else:
                raw = cast(NodeReturn[OutputT] | OutputT, raw_result)
            return _coerce_registry_result(
                node_name=self.name,
                output_model=self.output_model,
                default_outcome=_default_outcome(self),
                raw=cast(NodeReturn[BaseModel] | BaseModel, raw),
            )

        return handler


@overload
def node(
    fn: NodeCallable[InputT, OutputT] | AsyncNodeCallable[InputT, OutputT],
    /,
) -> NodeSpec[InputT, OutputT]: ...


@overload
def node(
    fn: None = None,
    /,
) -> Callable[
    [NodeCallable[InputT, OutputT] | AsyncNodeCallable[InputT, OutputT]],
    NodeSpec[InputT, OutputT],
]: ...


@overload
def node(
    fn: None = None,
    /,
    *,
    name: str | None = None,
    input_model: type[InputT] | None = None,
    output_model: type[OutputT] | None = None,
    outcomes: tuple[str, ...] = ("ok",),
    description: str | None = None,
    is_async: bool | None = None,
) -> Callable[
    [NodeCallable[InputT, OutputT] | AsyncNodeCallable[InputT, OutputT]],
    NodeSpec[InputT, OutputT],
]: ...


def node(
    fn: NodeCallable[InputT, OutputT]
    | AsyncNodeCallable[InputT, OutputT]
    | None = None,
    *,
    name: str | None = None,
    input_model: type[InputT] | None = None,
    output_model: type[OutputT] | None = None,
    outcomes: tuple[str, ...] = ("ok",),
    description: str | None = None,
    is_async: bool | None = None,
) -> Any:
    def decorator(
        fn: NodeCallable[InputT, OutputT] | AsyncNodeCallable[InputT, OutputT],
    ) -> NodeSpec[InputT, OutputT]:
        inferred_input_model: type[BaseModel] | None = input_model
        inferred_output_model: type[BaseModel] | None = output_model
        if inferred_input_model is None or inferred_output_model is None:
            inferred_input_model, inferred_output_model = _infer_models(fn)

        resolved_name = name or getattr(fn, "__name__", "node")
        resolved_is_async = iscoroutinefunction(fn) if is_async is None else is_async
        resolved_accepts_context = _accepts_context(fn)
        return cast(
            NodeSpec[InputT, OutputT],
            NodeSpec(
                name=resolved_name,
                input_model=inferred_input_model,
                output_model=inferred_output_model,
                outcomes=outcomes,
                fn=cast(Any, fn),
                description=description or fn.__doc__,
                is_async=resolved_is_async,
                accepts_context=resolved_accepts_context,
            ),
        )

    if fn is not None:
        return decorator(fn)
    return decorator


def build_registry(
    *specs: NodeSpec[Any, Any],
) -> dict[str, SyncRegistryHandler]:
    return _build_registry(specs, export="sync")


def build_async_registry(
    *specs: NodeSpec[Any, Any],
) -> dict[str, AsyncRegistryHandler]:
    return _build_registry(specs, export="async")


@overload
def _build_registry(
    specs: tuple[NodeSpec[Any, Any], ...],
    *,
    export: Literal["sync"],
) -> dict[str, SyncRegistryHandler]: ...


@overload
def _build_registry(
    specs: tuple[NodeSpec[Any, Any], ...],
    *,
    export: Literal["async"],
) -> dict[str, AsyncRegistryHandler]: ...


def _build_registry(
    specs: tuple[NodeSpec[Any, Any], ...],
    *,
    export: Literal["sync", "async"],
) -> dict[str, Any]:
    if export == "sync":
        return {spec.name: spec.to_registry_handler() for spec in specs}
    if export == "async":
        return {spec.name: spec.to_async_registry_handler() for spec in specs}
    raise ValueError(f"unknown registry export mode {export!r}")
