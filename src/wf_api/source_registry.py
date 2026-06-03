from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Generic, Protocol, TypeVar
from uuid import uuid4

from pydantic import BaseModel, ConfigDict


class SourceRegistryBaseModel(BaseModel):
    """Base model for persisted source registry state; reject misspelled fields."""

    model_config = ConfigDict(extra="forbid")


SOURCE_REGISTRY_ID_PATTERN = r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$"


def validate_source_registry_id(value: str) -> str:
    """Validate ids that are safe as registry keys and filesystem path segments.

    This helper intentionally does not parse provider/account meaning. MCP can
    layer stricter `parse_connection_id` validation on top while other future
    source families can reuse the safe-id rule.
    """

    if not re.fullmatch(SOURCE_REGISTRY_ID_PATTERN, value):
        raise ValueError(
            "source id must start with alphanumeric or underscore and contain "
            "only [A-Za-z0-9_.-]"
        )
    return value


def validate_unique_source_ids(entries: Sequence[object]) -> None:
    """Reject duplicate `id` fields without owning the entry model shape."""

    seen: set[str] = set()
    for entry in entries:
        source_id = getattr(entry, "id", None)
        if not isinstance(source_id, str):
            raise ValueError("source registry entries must expose string id")
        if source_id in seen:
            raise ValueError(f"duplicate source id {source_id!r}")
        seen.add(source_id)


RegistryT = TypeVar("RegistryT", bound=BaseModel)


class SourceRegistryStore(Protocol[RegistryT]):
    def load_registry(self) -> RegistryT: ...

    def save_registry(self, registry: RegistryT) -> None: ...


class AtomicJsonRegistryStore(Generic[RegistryT]):
    """Filesystem implementation for small desired-registry documents."""

    def __init__(
        self,
        root: Path,
        *,
        filename: str,
        registry_type: type[RegistryT],
        empty_factory: Callable[[], RegistryT],
        corrupt_label: str,
    ) -> None:
        self.root = root
        self.filename = filename
        self.registry_type = registry_type
        self.empty_factory = empty_factory
        self.corrupt_label = corrupt_label
        self.root.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self.root / self.filename

    def load_registry(self) -> RegistryT:
        if not self.path.exists():
            return self.empty_factory()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{self.corrupt_label} is corrupted: {self.path}") from exc
        return self.registry_type.model_validate(data)

    def save_registry(self, registry: RegistryT) -> None:
        validated = self.registry_type.model_validate(registry.model_dump(mode="json"))
        payload = json.dumps(validated.model_dump(mode="json"), indent=2)
        tmp_path = self.path.with_name(f"{self.path.name}.{uuid4().hex}.tmp")
        tmp_path.write_text(payload, encoding="utf-8")
        tmp_path.replace(self.path)


__all__ = [
    "AtomicJsonRegistryStore",
    "SourceRegistryBaseModel",
    "SourceRegistryStore",
    "SOURCE_REGISTRY_ID_PATTERN",
    "validate_source_registry_id",
    "validate_unique_source_ids",
]
