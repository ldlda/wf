from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field, TypeAdapter

from wf_core import Edge
from wf_core.models.steps import InputBinding, Step

type JsonObject = dict[str, Any]
type JsonSchema = dict[str, object]


class JsonProjector[T]:
    """Validate a dictionary projection once against its canonical JSON shape."""

    def __init__(self, schema: type[T]) -> None:
        self._adapter = TypeAdapter(schema)

    def __call__(self, value: object) -> T:
        return self._adapter.validate_python(value)


class HealthResult(TypedDict):
    """Health response shared by self-describing workflow transports."""

    status: Literal["ok"]
    store_root: str


class ArtifactVersionPayload(TypedDict):
    """Identity shared by results that refer to one immutable artifact version."""

    artifact_id: str
    artifact_version: int


class DependencyDiagnosticPayload(TypedDict):
    """JSON projection of one deployment dependency diagnostic."""

    severity: str
    code: str
    logical_ref: str
    bound_source: str | None
    message: str
    repair_hint: str | None


class NextActionPatchExamplePayload(TypedDict):
    """Concrete follow-up operation suggested to an API caller."""

    description: str
    tool: str
    request: JsonObject


class NextActionsPayload(TypedDict):
    """JSON projection of advisory workflow continuation guidance."""

    can_continue: bool
    can_save_now: bool | None
    recommended_next_tool: str | None
    reason: str
    patch_examples: list[NextActionPatchExamplePayload]
    warnings: list[str]


class GuidedResultPayload(TypedDict):
    """Diagnostics and continuation guidance shared by validated operations."""

    diagnostics: list[DependencyDiagnosticPayload]
    next_actions: NextActionsPayload


@dataclass(frozen=True, slots=True)
class TraceRange:
    """Caller-bounded debug trace slice for durable deployment runs."""

    start: int = 0
    limit: int = 25


class RawWorkflowPlan(BaseModel):
    """Raw authoring plan using the same graph step and edge models as core."""

    name: str
    input_schema: dict[str, Any]
    state_schema: dict[str, Any]
    output_schema: dict[str, Any]
    outcomes: list[str] = Field(
        default_factory=lambda: ["ok"],
        description=(
            "Declared public workflow outcomes. Legacy plans without this field "
            "default to ok."
        ),
    )
    output: list[InputBinding] = Field(
        default_factory=list,
        description=(
            "Optional root workflow output bindings. Sources read graph paths "
            "such as state.result and targets write the public output payload."
        ),
    )
    start: str
    nodes: list[Step]
    edges: list[Edge]
