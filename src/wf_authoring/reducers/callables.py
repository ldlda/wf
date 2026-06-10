from __future__ import annotations

from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

ConfigT = TypeVar("ConfigT", bound=BaseModel, infer_variance=True)


class PlainReducerCallable(Protocol):
    def __call__(self, current: Any, incoming: Any, /) -> Any: ...


class ConfigReducerCallable(Protocol[ConfigT]):
    def __call__(self, current: Any, incoming: Any, config: ConfigT, /) -> Any: ...
