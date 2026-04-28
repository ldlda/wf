from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from wf_core import NodeDef, RuntimeContext, SchemaRef

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)
NodeCallable = Callable[[InputT, RuntimeContext], "NodeReturn[OutputT] | OutputT"]
AsyncNodeCallable = Callable[
    [InputT, RuntimeContext], Awaitable["NodeReturn[OutputT] | OutputT"]
]


def _schema_ref_for(model_type: type[BaseModel]) -> SchemaRef:
    return SchemaRef.model_validate(model_type.model_json_schema())


@dataclass(slots=True)
class NodeReturn(Generic[OutputT]):
    outcome: str
    output: OutputT


@dataclass(slots=True)
class NodeSpec(Generic[InputT, OutputT]):
    name: str
    input_model: type[InputT]
    output_model: type[OutputT]
    outcomes: tuple[str, ...]
    fn: NodeCallable[InputT, OutputT] | AsyncNodeCallable[InputT, OutputT]
    description: str | None = None
    is_async: bool = False

    def __call__(
        self,
        payload: InputT,
        ctx: RuntimeContext,
    ) -> NodeReturn[OutputT] | OutputT | Awaitable[NodeReturn[OutputT] | OutputT]:
        return self.fn(payload, ctx)

    def to_node_def(self) -> NodeDef:
        return NodeDef(
            name=self.name,
            input_schema=_schema_ref_for(self.input_model),
            output_schema=_schema_ref_for(self.output_model),
            outcomes=list(self.outcomes),
        )

    def to_registry_handler(self) -> Callable[[dict[str, Any], RuntimeContext], dict[str, Any]]:
        if self.is_async:
            raise TypeError(
                f"node {self.name!r} is async and cannot be exported to the sync registry"
            )

        def handler(payload: dict[str, Any], ctx: RuntimeContext) -> dict[str, Any]:
            parsed = self.input_model.model_validate(payload)
            raw = self.fn(parsed, ctx)
            if isinstance(raw, NodeReturn):
                if not isinstance(raw.output, self.output_model):
                    raise TypeError(
                        f"node {self.name!r} returned NodeReturn with unsupported output "
                        f"{type(raw.output)!r}"
                    )
                return {
                    "outcome": raw.outcome,
                    "output": raw.output.model_dump(),
                }
            if isinstance(raw, self.output_model):
                return {"outcome": self.outcomes[0], "output": raw.model_dump()}
            raise TypeError(
                f"node {self.name!r} returned unsupported value {type(raw)!r}"
            )

        return handler


def node(
    *,
    name: str | None = None,
    input_model: type[InputT],
    output_model: type[OutputT],
    outcomes: tuple[str, ...] = ("ok",),
    description: str | None = None,
    is_async: bool = False,
) -> Callable[
    [NodeCallable[InputT, OutputT] | AsyncNodeCallable[InputT, OutputT]],
    NodeSpec[InputT, OutputT],
]:
    def decorator(
        fn: NodeCallable[InputT, OutputT] | AsyncNodeCallable[InputT, OutputT],
    ) -> NodeSpec[InputT, OutputT]:
        resolved_name = name or getattr(fn, "__name__", "node")
        return NodeSpec(
            name=resolved_name,
            input_model=input_model,
            output_model=output_model,
            outcomes=outcomes,
            fn=fn,
            description=description or fn.__doc__,
            is_async=is_async,
        )

    return decorator


def build_registry(
    *specs: NodeSpec[Any, Any],
) -> dict[str, Callable[[dict[str, Any], RuntimeContext], dict[str, Any]]]:
    return {spec.name: spec.to_registry_handler() for spec in specs}
