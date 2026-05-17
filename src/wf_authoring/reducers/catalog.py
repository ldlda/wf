from __future__ import annotations

from dataclasses import dataclass

from wf_core import ReducerSpec
from wf_core.runtime.ops.merges import ReducerDefinition

from .decorator import AuthoredReducer


@dataclass(frozen=True, slots=True)
class ReducerCatalog:
    """Collection of authored reducers ready for runtime and inventory use."""

    definitions: dict[str, ReducerDefinition]

    @classmethod
    def from_reducers(cls, *reducers: AuthoredReducer) -> "ReducerCatalog":
        return cls(
            definitions={
                reducer.definition.spec.name: reducer.definition for reducer in reducers
            }
        )

    @property
    def specs(self) -> dict[str, ReducerSpec]:
        return {name: definition.spec for name, definition in self.definitions.items()}
