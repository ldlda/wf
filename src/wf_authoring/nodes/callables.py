from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from wf_core import RuntimeContext

from .result import NodeReturn

InputT = TypeVar("InputT", bound=BaseModel, infer_variance=True)
OutputT = TypeVar("OutputT", bound=BaseModel, infer_variance=True)


class ContextNodeCallable(Protocol[InputT, OutputT]):
    def __call__(
        self,
        payload: InputT,
        /,
        ctx: RuntimeContext,
    ) -> NodeReturn[OutputT] | OutputT | None: ...


class PlainNodeCallable(Protocol[InputT, OutputT]):
    def __call__(
        self,
        payload: InputT,
        /,
    ) -> NodeReturn[OutputT] | OutputT | None: ...


NodeCallable = ContextNodeCallable[InputT, OutputT] | PlainNodeCallable[InputT, OutputT]


class AsyncContextNodeCallable(Protocol[InputT, OutputT]):
    def __call__(
        self,
        payload: InputT,
        /,
        ctx: RuntimeContext,
    ) -> Awaitable[NodeReturn[OutputT] | OutputT | None]: ...


class AsyncPlainNodeCallable(Protocol[InputT, OutputT]):
    def __call__(
        self,
        payload: InputT,
        /,
    ) -> Awaitable[NodeReturn[OutputT] | OutputT | None]: ...


AsyncNodeCallable = (
    AsyncContextNodeCallable[InputT, OutputT] | AsyncPlainNodeCallable[InputT, OutputT]
)

SyncRegistryHandler = Callable[[dict[str, Any], RuntimeContext], dict[str, Any]]
AsyncRegistryHandler = Callable[
    [dict[str, Any], RuntimeContext], Awaitable[dict[str, Any]]
]
