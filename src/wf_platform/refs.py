from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic_core import core_schema


@dataclass(frozen=True, slots=True)
class SourceRef:
    """Segment-backed source identifier with dotted-string wire formatting."""

    parts: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.parts or any(not part or not part.strip() for part in self.parts):
            raise ValueError("source ref requires non-empty path segments")

    @classmethod
    def parse(cls, value: str) -> SourceRef:
        """Parse one dotted source id into first-class path segments."""
        return cls(tuple(value.split(".")))

    def __str__(self) -> str:
        return ".".join(self.parts)

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: object,
        _handler: object,
    ) -> core_schema.CoreSchema:
        """Validate refs from strings while serializing back to wire strings."""
        return core_schema.no_info_plain_validator_function(
            cls._validate,
            serialization=core_schema.plain_serializer_function_ser_schema(
                str,
                when_used="json",
            ),
        )

    @classmethod
    def _validate(cls, value: Any) -> SourceRef:
        if isinstance(value, SourceRef):
            return value
        if isinstance(value, str):
            return cls.parse(value)
        if isinstance(value, Mapping):
            parts = value.get("parts")
            if isinstance(parts, list | tuple) and all(
                isinstance(part, str) for part in parts
            ):
                return cls(tuple(parts))
        raise TypeError("source ref must be a string")


@dataclass(frozen=True, slots=True)
class CapabilityRef:
    """Segment-backed capability reference: one source plus one local name."""

    source: SourceRef
    name: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("capability ref requires a non-empty name")

    @classmethod
    def parse(cls, value: str) -> CapabilityRef:
        """Parse `<source>.<capability>` while preserving source path segments."""
        source_text, separator, name = value.rpartition(".")
        if not separator or not source_text or not name:
            raise ValueError("capability ref requires source and capability segments")
        return cls(source=SourceRef.parse(source_text), name=name)

    def bind(self, bindings: Mapping[str, str]) -> CapabilityRef:
        """Replace a logical source with its concrete bound source when present."""
        bound_source = bindings.get(str(self.source))
        if bound_source is None:
            return self
        return CapabilityRef(source=SourceRef.parse(bound_source), name=self.name)

    def __str__(self) -> str:
        return f"{self.source}.{self.name}"

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: object,
        _handler: object,
    ) -> core_schema.CoreSchema:
        """Validate refs from strings while serializing back to wire strings."""
        return core_schema.no_info_plain_validator_function(
            cls._validate,
            serialization=core_schema.plain_serializer_function_ser_schema(
                cls._serialize,
                when_used="json",
            ),
        )

    @classmethod
    def _validate(cls, value: Any) -> CapabilityRef:
        if isinstance(value, CapabilityRef):
            return value
        if isinstance(value, str):
            return cls.parse(value)
        if isinstance(value, dict):
            source = value.get("source")
            name = value.get("capability_key", value.get("name"))
            if isinstance(name, str):
                return cls(source=SourceRef._validate(source), name=name)
        raise TypeError(
            "capability ref must be a string or {'source': str, 'capability_key': str}"
        )

    @staticmethod
    def _serialize(value: CapabilityRef) -> dict[str, str]:
        """Serialize canonical saved refs structurally; `str(ref)` is display-only."""
        return {"source": str(value.source), "capability_key": value.name}
