from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from wf_core.models.steps import StepInputBinding


class CapabilityStepUpdate(BaseModel):
    """Presence-aware patch for one existing capability-backed draft step."""

    model_config = ConfigDict(extra="forbid")

    desc: str | None = Field(default=None, min_length=1)
    retry: int | None = Field(default=None, ge=0)
    timeout_seconds: int | None = Field(default=None, gt=0)
    input: list[StepInputBinding] | None = None

    @model_validator(mode="after")
    def validate_patch_shape(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("capability step update requires at least one field")
        if "input" in self.model_fields_set and self.input is None:
            raise ValueError("capability step update input must be a list")
        return self
