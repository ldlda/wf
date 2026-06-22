from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from difflib import get_close_matches
from functools import cache
from typing import Any, TypeAlias

from jsonschema import Draft202012Validator
from pydantic import TypeAdapter

from wf_api.models import RawWorkflowPlan
from wf_artifacts.drafts.models import WorkflowDraft
from wf_core.models.workflow import Workflow


JsonObject: TypeAlias = dict[str, Any]
SCHEMA_DIALECT = Draft202012Validator.META_SCHEMA["$id"]
ROOT_MODELS: dict[str, type[Any]] = {
    "WorkflowDraft": WorkflowDraft,
    "RawWorkflowPlan": RawWorkflowPlan,
    "Workflow": Workflow,
}
ALIASES = {
    "draft": "WorkflowDraft",
    "raw": "RawWorkflowPlan",
    "core": "Workflow",
}


@dataclass(frozen=True, slots=True)
class SchemaEntry:
    name: str
    aliases: tuple[str, ...]
    kind: str
    description: str | None


@dataclass(frozen=True, slots=True)
class SchemaCatalog:
    roots: dict[str, JsonObject]
    definitions: dict[str, JsonObject]
    aliases: dict[str, str]

    def resolve(self, name: str) -> str:
        canonical = self.aliases.get(name, name)
        if canonical in self.roots or canonical in self.definitions:
            return canonical
        choices = sorted({*self.aliases, *self.roots, *self.definitions})
        suggestion = get_close_matches(name, choices, n=1)
        message = f"unknown schema {name!r}"
        if suggestion:
            message += f". Did you mean {suggestion[0]!r}?"
        raise KeyError(message)

    def schema(self, name: str) -> JsonObject:
        canonical = self.resolve(name)
        source = self.roots.get(canonical, self.definitions.get(canonical))
        if source is None:
            raise KeyError(canonical)
        return deepcopy(source)

    def entry(self, name: str) -> SchemaEntry:
        canonical = self.resolve(name)
        schema = self.schema(canonical)
        aliases = tuple(sorted(alias for alias, target in self.aliases.items() if target == canonical))
        return SchemaEntry(
            name=canonical,
            aliases=aliases,
            kind="root" if canonical in self.roots else "definition",
            description=schema.get("description"),
        )

    def entries(self) -> list[SchemaEntry]:
        names = sorted({*self.roots, *self.definitions})
        return [self.entry(name) for name in names]


@cache
def schema_catalog() -> SchemaCatalog:
    roots = {
        name: TypeAdapter(model).json_schema(mode="validation", by_alias=True)
        for name, model in ROOT_MODELS.items()
    }
    combined = TypeAdapter(WorkflowDraft | RawWorkflowPlan | Workflow).json_schema(
        mode="validation", by_alias=True
    )
    raw_definitions = combined.get("$defs", {})
    if not isinstance(raw_definitions, dict):
        raise RuntimeError("combined workflow schema has no object $defs table")
    definitions = {name: deepcopy(value) for name, value in raw_definitions.items()}
    for root in roots.values():
        root_definitions = root.get("$defs", {})
        if not isinstance(root_definitions, dict):
            raise RuntimeError("workflow root schema has non-object $defs")
        for name, value in root_definitions.items():
            existing = definitions.get(name)
            if existing is not None and existing != value:
                raise RuntimeError(f"conflicting workflow schema definition: {name}")
            definitions.setdefault(name, deepcopy(value))
    return SchemaCatalog(roots=roots, definitions=definitions, aliases=dict(ALIASES))
