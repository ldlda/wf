from __future__ import annotations

from collections.abc import Mapping
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator


class WorkflowRef(BaseModel):
    """Structural reference to a child workflow contract.

    Core needs a workflow reference for graph shape and validation, but it must
    not depend on artifact stores or MCP capability naming. Saved workflow
    artifacts can use ``artifact_id`` plus ``version``; local compiled workflows
    can use ``name``. Legacy strings parse as ``name`` unless they use the old
    ``workflow.<artifact>.v<version>`` display format.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, description="Local workflow registry name.")
    artifact_id: str | None = Field(
        default=None,
        description="Saved workflow artifact id, when referencing an immutable artifact.",
    )
    version: int | None = Field(
        default=None,
        ge=1,
        description="Saved workflow artifact version. Requires artifact_id.",
    )

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_strings(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        try:
            artifact_id, version = _parse_legacy_workflow_capability(value)
        except ValueError:
            return {"name": value}
        return {"artifact_id": artifact_id, "version": version}

    @model_validator(mode="after")
    def _validate_one_ref_kind(self) -> Self:
        has_name = self.name is not None
        has_artifact = self.artifact_id is not None or self.version is not None
        if has_name == has_artifact:
            raise ValueError(
                "workflow ref requires exactly one of name or artifact_id/version"
            )
        if has_artifact and (self.artifact_id is None or self.version is None):
            raise ValueError(
                "workflow artifact ref requires both artifact_id and version"
            )
        if self.name is not None and not self.name.strip():
            raise ValueError("workflow ref name must not be empty")
        if self.artifact_id is not None and not self.artifact_id.strip():
            raise ValueError("workflow artifact id must not be empty")
        return self

    @property
    def display(self) -> str:
        """Return a human-readable compatibility name; do not parse this for meaning."""
        if self.name is not None:
            return self.name
        return f"workflow.{self.artifact_id}.v{self.version}"

    @model_serializer(mode="wrap")
    def _serialize_without_none_fields(self, handler: object) -> dict[str, object]:
        """Persist only the active ref shape."""
        if not callable(handler):
            raise TypeError("workflow ref serializer handler must be callable")
        data = handler(self)
        if not isinstance(data, dict):
            raise TypeError("workflow ref serializer expected a dict")
        return {key: value for key, value in data.items() if value is not None}


def workflow_ref_from(value: WorkflowRef | str | Mapping[str, object]) -> WorkflowRef:
    """Normalize public helper inputs into the core workflow ref model."""
    return WorkflowRef.model_validate(value)


def _parse_legacy_workflow_capability(value: str) -> tuple[str, int]:
    prefix = "workflow."
    if not value.startswith(prefix):
        raise ValueError("not a workflow artifact display ref")
    artifact_part, separator, version_part = value[len(prefix) :].rpartition(".v")
    if not separator or not artifact_part or not version_part.isdecimal():
        raise ValueError("not a workflow artifact display ref")
    return artifact_part, int(version_part)
