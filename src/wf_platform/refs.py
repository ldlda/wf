from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SourceRef:
    """Segment-backed source identifier with dotted-string wire formatting."""

    parts: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.parts or any(not part for part in self.parts):
            raise ValueError("source ref requires non-empty path segments")

    @classmethod
    def parse(cls, value: str) -> SourceRef:
        """Parse one dotted source id into first-class path segments."""
        return cls(tuple(value.split(".")))

    def __str__(self) -> str:
        return ".".join(self.parts)


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
