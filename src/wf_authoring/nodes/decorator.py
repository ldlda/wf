from __future__ import annotations

from inspect import iscoroutinefunction
from collections.abc import Callable
from typing import Any, cast, overload

from pydantic import BaseModel

from .callables import AsyncNodeCallable, InputT, NodeCallable, OutputT
from .inference import accepts_context, infer_models
from .spec import NodeSpec


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
    """Convert a typed Python function into a reusable workflow node spec."""
    def decorator(
        fn: NodeCallable[InputT, OutputT] | AsyncNodeCallable[InputT, OutputT],
    ) -> NodeSpec[InputT, OutputT]:
        inferred_input_model: type[BaseModel] | None = input_model
        inferred_output_model: type[BaseModel] | None = output_model
        if inferred_input_model is None or inferred_output_model is None:
            inferred_input_model, inferred_output_model = infer_models(fn)

        resolved_name = name or getattr(fn, "__name__", "node")
        resolved_is_async = iscoroutinefunction(fn) if is_async is None else is_async
        resolved_accepts_context = accepts_context(fn)
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
