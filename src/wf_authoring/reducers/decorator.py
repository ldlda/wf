from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, cast, overload

from wf_core import ReducerSpec, SiblingWritePolicy
from wf_core.runtime.ops.merges import ReducerDefinition

from .callables import ConfigReducerCallable, ConfigT, PlainReducerCallable


@dataclass(frozen=True, slots=True)
class AuthoredReducer:
    """Authoring wrapper for one reducer implementation."""

    definition: ReducerDefinition


# @reducer no parentheses / manual overload
@overload
def reducer(
    fn: PlainReducerCallable,
    /,
    *,
    name: str | None = None,
    description: str | None = None,
    sibling_write_policy: SiblingWritePolicy = SiblingWritePolicy.MERGEABLE,
) -> AuthoredReducer: ...


@overload
def reducer(
    fn: ConfigReducerCallable[ConfigT],
    /,
    *,
    name: str | None = None,
    config_model: type[ConfigT],
    description: str | None = None,
    sibling_write_policy: SiblingWritePolicy = SiblingWritePolicy.MERGEABLE,
) -> AuthoredReducer: ...


# configless overload
@overload
def reducer(
    *,
    name: str,
    description: str | None = None,
    sibling_write_policy: SiblingWritePolicy = SiblingWritePolicy.MERGEABLE,
) -> Callable[[PlainReducerCallable], AuthoredReducer]: ...


# config overload
@overload
def reducer(
    *,
    name: str,
    config_model: type[ConfigT],
    description: str | None = None,
    sibling_write_policy: SiblingWritePolicy = SiblingWritePolicy.MERGEABLE,
) -> Callable[[ConfigReducerCallable[ConfigT]], AuthoredReducer]: ...


def reducer(
    fn: PlainReducerCallable | ConfigReducerCallable[ConfigT] | None = None,
    /,
    *,
    name: str | None = None,
    config_model: type[ConfigT] | None = None,
    description: str | None = None,
    sibling_write_policy: SiblingWritePolicy = SiblingWritePolicy.MERGEABLE,
) -> (
    AuthoredReducer
    | Callable[[PlainReducerCallable], AuthoredReducer]
    | Callable[[ConfigReducerCallable[ConfigT]], AuthoredReducer]
):
    """Wrap a Python reducer function as a runtime reducer definition.

    Assume wrapped function will not approve of the third `config` argument if `config_model` is not provided, and vice versa
    """
    # how do i even do this...
    # if @overload return is (PlainReducerCallable) -> Authored. (or even another is (ConfigReducerCallable[ConfigT]) -> Authored). then the base signature must not be (Plain | Config) -> Authored???
    # why is that, basedpyright?

    if config_model is None:

        def decorate_plain(
            raw: PlainReducerCallable,
        ) -> AuthoredReducer:
            reducer_name = name or getattr(raw, "__name__", "<anonymous plain reducer>")
            reducer_description = description or raw.__doc__
            # if no config model is provided, we assume it's a plain reducer and just wrap it directly
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

        # fail-fast? worse treatment than @node
        if fn is not None:
            return decorate_plain(cast(PlainReducerCallable, fn))
        return decorate_plain

    else:

        def decorate_config(
            raw: ConfigReducerCallable[ConfigT],
        ) -> AuthoredReducer:
            reducer_name = name or getattr(raw, "__name__", "<anonymous config reducer>")
            reducer_description = description or raw.__doc__

            model_type = config_model

            # if a config model is provided, we need to parse the config before calling the reducer function
            def runtime_fn(
                current: Any,
                incoming: Any,
                config: Mapping[str, Any],
            ) -> Any:
                parsed = model_type.model_validate(config)
                return raw(
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
            return decorate_config(cast(ConfigReducerCallable[ConfigT], fn))
        return decorate_config


def _clean_doc(doc: str | None) -> str | None:
    if doc is None:
        return None
    cleaned = doc.strip()
    return cleaned or None
