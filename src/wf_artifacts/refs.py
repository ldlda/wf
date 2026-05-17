from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkflowCapabilityRef:
    """Stable public capability name for one saved workflow artifact version."""

    artifact_id: str
    version: int

    def __post_init__(self) -> None:
        if not self.artifact_id:
            raise ValueError("workflow capability ref requires an artifact id")
        if self.version < 1:
            raise ValueError("workflow capability ref requires version >= 1")

    @classmethod
    def parse(cls, value: str) -> WorkflowCapabilityRef:
        """Parse `workflow.<artifact_id>.v<version>` into first-class fields."""
        prefix = "workflow."
        if not value.startswith(prefix):
            raise ValueError("workflow capability ref must use the workflow namespace")
        artifact_part, separator, version_part = value[len(prefix) :].rpartition(".v")
        if not separator or not artifact_part or not version_part.isdecimal():
            raise ValueError(
                "workflow capability ref must be workflow.<artifact_id>.v<version>"
            )
        return cls(artifact_id=artifact_part, version=int(version_part))

    def __str__(self) -> str:
        return f"workflow.{self.artifact_id}.v{self.version}"
