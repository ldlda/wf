from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic_core import core_schema

from wf_core import WorkflowRef

from .models import WorkflowArtifact


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

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: object,
        _handler: object,
    ) -> core_schema.CoreSchema:
        """Validate legacy display strings but save workflow refs structurally."""
        return core_schema.no_info_plain_validator_function(
            cls._validate,
            serialization=core_schema.plain_serializer_function_ser_schema(
                cls._serialize,
                when_used="json",
            ),
        )

    @classmethod
    def _validate(cls, value: Any) -> WorkflowCapabilityRef:
        if isinstance(value, WorkflowCapabilityRef):
            return value
        if isinstance(value, str):
            return cls.parse(value)
        if isinstance(value, dict):
            artifact_id = value.get("artifact_id")
            version = value.get("version")
            if isinstance(artifact_id, str) and isinstance(version, int):
                return cls(artifact_id=artifact_id, version=version)
        raise TypeError(
            "workflow capability ref must be a workflow.<artifact>.v<version> "
            "string or {'artifact_id': str, 'version': int}"
        )

    @staticmethod
    def _serialize(value: WorkflowCapabilityRef) -> dict[str, int | str]:
        """Serialize canonical saved workflow refs without a display-name parser."""
        return {"artifact_id": value.artifact_id, "version": value.version}


def workflow_ref_from_artifact(artifact: WorkflowArtifact) -> WorkflowRef:
    """Return the core child-workflow ref for one saved artifact version."""
    return WorkflowRef(artifact_id=artifact.id, version=artifact.version)


def workflow_ref_from_capability(ref: WorkflowCapabilityRef) -> WorkflowRef:
    """Return the core child-workflow ref for a workflow capability identity."""
    return WorkflowRef(artifact_id=ref.artifact_id, version=ref.version)


def workflow_capability_ref_from_workflow_ref(
    ref: WorkflowRef,
) -> WorkflowCapabilityRef:
    """Return the public capability ref for an artifact-backed workflow ref."""
    if ref.artifact_id is None or ref.version is None:
        raise ValueError("workflow capability refs require an artifact workflow ref")
    return WorkflowCapabilityRef(artifact_id=ref.artifact_id, version=ref.version)
