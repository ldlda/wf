"""Rich, transport-independent objects for remote workflow capabilities."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from jsonschema import Draft202012Validator, SchemaError, ValidationError

from wf_artifacts.models import DependencyDiagnostic
from wf_core.models.schemas import NodeDef, SchemaRef
from wf_platform import CapabilityRef

from .codec import decode_capability_call, decode_capability_diagnostics
from .errors import InvalidResponse
from .protocols import WorkflowClientPort


@dataclass(frozen=True, slots=True)
class CapabilitySummary:
    """Compact immutable discovery row for a planner-visible capability."""

    qualified_name: str
    source_id: str
    kind: str
    description: str | None
    outcomes: tuple[str, ...]
    is_async: bool
    input_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    artifact_id: str | None = None
    version: int | None = None
    title: str | None = None

    @property
    def name(self) -> str:
        """Compatibility alias for the wire row's ``name`` field."""
        return self.qualified_name


@dataclass(frozen=True, slots=True)
class CapabilityResult:
    """Validated result of invoking one remote capability."""

    outcome: str
    output: dict[str, Any] | None
    diagnostics: tuple[DependencyDiagnostic, ...]


def _check_schema(schema: object, *, operation: str) -> dict[str, Any]:
    if not isinstance(schema, Mapping):
        raise InvalidResponse(
            operation=operation,
            details="capability schema must be a JSON object",
        )
    schema_copy = deepcopy(dict(schema))
    try:
        Draft202012Validator.check_schema(schema_copy)
    except SchemaError as exc:
        raise InvalidResponse(
            operation=operation,
            details=f"invalid JSON Schema: {exc.message}",
        ) from exc
    return schema_copy


@dataclass(frozen=True, slots=True)
class RemoteCapability:
    """Inspected remote capability that validates calls against its contract."""

    _port: WorkflowClientPort = field(repr=False, compare=False)
    ref: CapabilityRef
    qualified_name: str
    description: str | None
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    outcomes: tuple[str, ...]
    is_async: bool

    def __post_init__(self) -> None:
        # Freeze the public container shape at construction. The nested JSON
        # values remain ordinary JSON objects because callers expect to inspect
        # and pass schemas directly to existing pydantic/core APIs.
        if not self.outcomes:
            raise InvalidResponse(
                operation="workflow.capabilities.inspect",
                details="capability contract must declare at least one outcome",
            )
        object.__setattr__(
            self,
            "input_schema",
            _check_schema(
                self.input_schema,
                operation="workflow.capabilities.inspect",
            ),
        )
        object.__setattr__(
            self,
            "output_schema",
            _check_schema(
                self.output_schema,
                operation="workflow.capabilities.inspect",
            ),
        )
        object.__setattr__(self, "outcomes", tuple(self.outcomes))

    async def __call__(
        self,
        payload: Mapping[str, Any] | None = None,
        /,
        **fields: Any,
    ) -> CapabilityResult:
        if payload is not None and fields:
            raise TypeError("pass a payload mapping or keyword fields, not both")
        return await self.call(dict(payload) if payload is not None else fields)

    async def call(
        self,
        payload: Mapping[str, Any],
        *,
        deployment_id: str | None = None,
    ) -> CapabilityResult:
        """Validate input locally, invoke remotely, and validate its result."""
        input_payload = dict(payload)
        input_validator = Draft202012Validator(self.input_schema)
        # jsonschema.ValidationError intentionally remains the local input
        # error: no transport operation has happened when it is raised.
        input_validator.validate(input_payload)

        wire = decode_capability_call(
            await self._port.call_capability(
                qualified_name=self.qualified_name,
                payload=input_payload,
                deployment_id=deployment_id,
            )
        )
        if wire["qualified_name"] != self.qualified_name:
            raise InvalidResponse(
                operation="workflow.capabilities.call",
                details=(
                    f"result qualified name {wire['qualified_name']!r} does not "
                    f"match requested {self.qualified_name!r}"
                ),
            )
        if wire["outcome"] not in self.outcomes:
            raise InvalidResponse(
                operation="workflow.capabilities.call",
                details=f"unknown capability outcome {wire['outcome']!r}",
            )

        output = wire["output"]
        if output is not None:
            try:
                Draft202012Validator(self.output_schema).validate(output)
            except ValidationError as exc:
                # Schema validation errors are expected server-contract
                # failures; do not leak jsonschema internals as public output.
                raise InvalidResponse(
                    operation="workflow.capabilities.call",
                    details=f"output does not match capability schema: {exc}",
                ) from exc
        return CapabilityResult(
            outcome=wire["outcome"],
            output=deepcopy(output) if output is not None else None,
            diagnostics=decode_capability_diagnostics(wire["diagnostics"]),
        )

    def node_def(self) -> NodeDef:
        """Return the schema contract consumed by ``WorkflowBuilder.use_contract``."""
        return NodeDef(
            name=self.qualified_name,
            input_schema=SchemaRef.model_validate(deepcopy(self.input_schema)),
            output_schema=SchemaRef.model_validate(deepcopy(self.output_schema)),
            outcomes=list(self.outcomes),
        )
