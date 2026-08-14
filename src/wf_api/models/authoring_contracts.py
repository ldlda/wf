from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

from .common import JsonObject

type AuthoringPathOrigin = Literal[
    "workflow_input",
    "workflow_state",
    "runtime_context",
    "step_input",
    "step_output",
    "workflow_output",
]
type AuthoringPathAvailability = Literal["available", "conditional"]
type AuthoringPathUse = Literal[
    "step_input",
    "step_output_source",
    "state_target",
    "workflow_output",
]


class AuthoringPathOptionPayload(TypedDict):
    """One schema-derived source or target available to an author."""

    path: str
    label: str
    origin: AuthoringPathOrigin
    schema: JsonObject
    required: bool
    availability: AuthoringPathAvailability
    uses: list[AuthoringPathUse]
    description: NotRequired[str]
    reason: NotRequired[str]


class AuthoringStepContractPayload(TypedDict):
    """Compact executable-step choice used by authoring inventories."""

    step_id: str
    label: str
    description: NotRequired[str]
    input_targets: NotRequired[list[AuthoringPathOptionPayload]]
    output_sources: NotRequired[list[AuthoringPathOptionPayload]]
    outcomes: NotRequired[list[str]]


class AuthoringContractInventoryPayload(TypedDict):
    """Revision-scoped readable sources and writable authoring targets."""

    workspace_id: str
    revision: int
    selected_step_id: str | None
    readable_sources: list[AuthoringPathOptionPayload]
    step_input_targets: list[AuthoringPathOptionPayload]
    step_output_sources: list[AuthoringPathOptionPayload]
    state_targets: list[AuthoringPathOptionPayload]
    workflow_output_targets: list[AuthoringPathOptionPayload]
    entry_steps: list[AuthoringStepContractPayload]
    workflow_outcomes: list[str]
    warnings: list[str]
