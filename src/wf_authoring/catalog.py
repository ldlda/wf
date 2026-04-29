from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .spec import NodeSpec


@dataclass(slots=True)
class NodeCatalogEntry:
    name: str
    description: str | None
    outcomes: tuple[str, ...]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]

    @classmethod
    def from_spec(cls, spec: NodeSpec[Any, Any]) -> "NodeCatalogEntry":
        return cls(
            name=spec.name,
            description=spec.description,
            outcomes=spec.outcomes,
            input_schema=spec.input_model.model_json_schema(),
            output_schema=spec.output_model.model_json_schema(),
        )


@dataclass(slots=True)
class NodeCatalog:
    specs: dict[str, NodeSpec[Any, Any]]

    @classmethod
    def from_specs(cls, *specs: NodeSpec[Any, Any]) -> "NodeCatalog":
        return cls(specs={spec.name: spec for spec in specs})

    def entries(self) -> list[NodeCatalogEntry]:
        return [NodeCatalogEntry.from_spec(spec) for spec in self.specs.values()]

    def as_mcp_payload(self) -> dict[str, Any]:
        return {
            "nodes": [
                {
                    "name": entry.name,
                    "description": entry.description,
                    "outcomes": list(entry.outcomes),
                    "input_schema": entry.input_schema,
                    "output_schema": entry.output_schema,
                }
                for entry in self.entries()
            ]
        }
