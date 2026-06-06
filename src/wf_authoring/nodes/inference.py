from __future__ import annotations

from collections.abc import Callable
from inspect import Parameter, signature
from typing import cast, get_args, get_origin, get_type_hints

from pydantic import BaseModel

from wf_core import RuntimeContext

from .result import NodeReturn, Nothing


def is_basemodel_subclass(value: object) -> bool:
    return isinstance(value, type) and issubclass(value, BaseModel)


def infer_models(fn: Callable[..., object]) -> tuple[type[BaseModel], type[BaseModel]]:
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
    if not is_basemodel_subclass(input_model):
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
    if return_type is type(None):
        return cast(type[BaseModel], input_model), Nothing

    if is_basemodel_subclass(return_type):
        return cast(type[BaseModel], input_model), cast(type[BaseModel], return_type)

    if return_type is NodeReturn:
        return cast(type[BaseModel], input_model), Nothing

    origin = get_origin(return_type)
    if origin is NodeReturn:
        args = get_args(return_type)
        if len(args) != 1 or not is_basemodel_subclass(args[0]):
            raise TypeError(
                "NodeReturn return annotation must wrap a BaseModel subclass"
            )
        return cast(type[BaseModel], input_model), cast(type[BaseModel], args[0])

    raise TypeError(
        "node return annotation must be a BaseModel subclass or NodeReturn[BaseModel]"
    )


def accepts_context(fn: Callable[..., object]) -> bool:
    return len(signature(fn).parameters) >= 2
