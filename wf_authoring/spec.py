from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from wf_core import NodeDef, RuntimeContext, SchemaRef

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


def _schema_ref_for(model_type: type[BaseModel]) -> SchemaRef:
    return SchemaRef.model_validate(model_type.model_json_schema())


@dataclass(slots=True)
class NodeSpec(Generic[InputT, OutputT]):
    name: str
    input_model: type[InputT]
    output_model: type[OutputT]
    outcomes: tuple[str, ...]
    fn: Callable[[InputT, RuntimeContext], OutputT | dict[str, Any]]
    description: str | None = None
    is_async: bool = False

    def __call__(
        self,
        payload: InputT,
        ctx: RuntimeContext,
    ) -> OutputT | dict[str, Any]:
        return self.fn(payload, ctx)

    def to_node_def(self) -> NodeDef:
        return NodeDef(
            name=self.name,
            input_schema=_schema_ref_for(self.input_model),
            output_schema=_schema_ref_for(self.output_model),
            outcomes=list(self.outcomes),
        )

    def to_registry_handler(self) -> Callable[[dict[str, Any], RuntimeContext], dict[str, Any]]:
        def handler(payload: dict[str, Any], ctx: RuntimeContext) -> dict[str, Any]:
            parsed = self.input_model.model_validate(payload)
            raw = self.fn(parsed, ctx)
            if isinstance(raw, self.output_model):
                return {"outcome": self.outcomes[0], "output": raw.model_dump()}
            if isinstance(raw, dict):
                return raw
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
) -> Callable[
    [Callable[[InputT, RuntimeContext], OutputT | dict[str, Any]]],
    NodeSpec[InputT, OutputT],
]:
    def decorator(
        fn: Callable[[InputT, RuntimeContext], OutputT | dict[str, Any]],
    ) -> NodeSpec[InputT, OutputT]:
        resolved_name = name or getattr(fn, "__name__", "node")
        return NodeSpec(
            name=resolved_name,
            input_model=input_model,
            output_model=output_model,
            outcomes=outcomes,
            fn=fn,
            description=description or fn.__doc__,
            is_async=False,
        )

    return decorator
