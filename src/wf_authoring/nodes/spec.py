from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Any, Generic, cast

from pydantic import BaseModel

from wf_core import NodeDef, RuntimeContext

from .callables import (
    AsyncNodeCallable,
    AsyncRegistryHandler,
    ContextNodeCallable,
    InputT,
    NodeCallable,
    OutputT,
    PlainNodeCallable,
    SyncRegistryHandler,
)
from .result import NodeReturn
from .schema import schema_ref_for


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


@dataclass(slots=True)
class NodeSpec(Generic[InputT, OutputT]):
    """Authoring-time wrapper for a typed Python node function."""

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
            input_schema=schema_ref_for(self.input_model),
            output_schema=schema_ref_for(self.output_model),
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
