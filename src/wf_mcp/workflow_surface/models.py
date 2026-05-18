from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class CallCapabilityResult(BaseModel):
    """Inspector-visible response contract for testing one workflow capability."""

    qualified_name: str = Field(description="Capability name that was executed.")
    source_id: str | None = Field(
        default=None,
        description="Capability source that owned the executed node spec.",
    )
    kind: Literal["node_spec", "wrapper_artifact"] = Field(
        description=(
            "Indicates whether this call executed a live NodeSpec or a saved "
            "wrapper artifact."
        )
    )
    deployment_id: str | None = Field(
        default=None,
        description="Deployment used to resolve logical bindings, if any.",
    )
    outcome: str = Field(description="Workflow outcome returned by the capability.")
    output: dict[str, Any] | None = Field(
        default=None,
        description="Normalized workflow-facing output payload.",
    )
    diagnostics: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Structured diagnostics. Empty for successful calls.",
    )
