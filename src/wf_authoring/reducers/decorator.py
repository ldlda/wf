from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, TypeVar, cast, overload

from pydantic import BaseModel

from wf_core import ReducerSpec, SiblingWritePolicy
from wf_core.runtime.ops.merges import ReducerDefinition

from .callables import ConfigReducerCallable, ConfigT, PlainReducerCallable

PlainFnT = TypeVar("PlainFnT", bound=PlainReducerCallable)


@dataclass(frozen=True, slots=True)
class AuthoredReducer:
    """Authoring wrapper for one reducer implementation."""

    definition: ReducerDefinition


@overload
def reducer(
    fn: PlainFnT,
    /,
    *,
    name: str | None = None,
    description: str | None = None,
    sibling_write_policy: SiblingWritePolicy = SiblingWritePolicy.MERGEABLE,
) -> AuthoredReducer: ...


@overload
def reducer(
    *,
    name: str,
    description: str | None = None,
    sibling_write_policy: SiblingWritePolicy = SiblingWritePolicy.MERGEABLE,
) -> Callable[[Callable[..., Any]], AuthoredReducer]: ...


@overload
def reducer(
    *,
    name: str,
    config_model: type[ConfigT],
    description: str | None = None,
    sibling_write_policy: SiblingWritePolicy = SiblingWritePolicy.MERGEABLE,
) -> Callable[[Callable[..., Any]], AuthoredReducer]: ...


def reducer(
    fn: Callable[..., Any] | None = None,
    /,
    *,
    name: str | None = None,
    config_model: type[BaseModel] | None = None,
    description: str | None = None,
    sibling_write_policy: SiblingWritePolicy = SiblingWritePolicy.MERGEABLE,
) -> AuthoredReducer | Callable[[Callable[..., Any]], AuthoredReducer]:
    """Wrap a Python reducer function as a runtime reducer definition."""

    def decorate(raw: Callable[..., Any]) -> AuthoredReducer:
        reducer_name = name or raw.__name__
        reducer_description = description or raw.__doc__
        if config_model is None:
            return AuthoredReducer(
                ReducerDefinition(
                    spec=ReducerSpec(
                        name=reducer_name,
                        description=_clean_doc(reducer_description),
                        sibling_write_policy=sibling_write_policy,
                    ),
                    fn=raw,
                )
            )

        model_type = config_model

        def runtime_fn(
            current: Any,
            incoming: Any,
            config: Mapping[str, Any],
        ) -> Any:
            parsed = model_type.model_validate(config)
            return cast(ConfigReducerCallable[BaseModel], cast(object, raw))(
                current,
                incoming,
                parsed,
            )

        return AuthoredReducer(
            ReducerDefinition(
                spec=ReducerSpec(
                    name=reducer_name,
                    description=_clean_doc(reducer_description),
                    config_schema=config_model.model_json_schema(),
                    sibling_write_policy=sibling_write_policy,
                ),
                fn=runtime_fn,
                accepts_config=True,
            )
        )

    if fn is not None:
        return decorate(fn)
    return decorate


def _clean_doc(doc: str | None) -> str | None:
    if doc is None:
        return None
    cleaned = doc.strip()
    return cleaned or None
