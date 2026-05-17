from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from wf_core import RuntimeContext

from .result import NodeReturn

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)

InputT_contra = TypeVar("InputT_contra", bound=BaseModel, contravariant=True)
OutputT_co = TypeVar("OutputT_co", bound=BaseModel, covariant=True)


class ContextNodeCallable(Protocol[InputT_contra, OutputT_co]):
    def __call__(
        self,
        payload: InputT_contra,
        /,
        ctx: RuntimeContext,
    ) -> NodeReturn[OutputT_co] | OutputT_co | None: ...


class PlainNodeCallable(Protocol[InputT_contra, OutputT_co]):
    def __call__(
        self,
        payload: InputT_contra,
        /,
    ) -> NodeReturn[OutputT_co] | OutputT_co | None: ...


NodeCallable = ContextNodeCallable[InputT, OutputT] | PlainNodeCallable[InputT, OutputT]


class AsyncContextNodeCallable(Protocol[InputT_contra, OutputT_co]):
    def __call__(
        self,
        payload: InputT_contra,
        /,
        ctx: RuntimeContext,
    ) -> Awaitable[NodeReturn[OutputT_co] | OutputT_co | None]: ...


class AsyncPlainNodeCallable(Protocol[InputT_contra, OutputT_co]):
    def __call__(
        self,
        payload: InputT_contra,
        /,
    ) -> Awaitable[NodeReturn[OutputT_co] | OutputT_co | None]: ...


AsyncNodeCallable = (
    AsyncContextNodeCallable[InputT, OutputT] | AsyncPlainNodeCallable[InputT, OutputT]
)

SyncRegistryHandler = Callable[[dict[str, Any], RuntimeContext], dict[str, Any]]
AsyncRegistryHandler = Callable[
    [dict[str, Any], RuntimeContext], Awaitable[dict[str, Any]]
]
