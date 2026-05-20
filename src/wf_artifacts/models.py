from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from wf_platform import CapabilityRef, SourceRef

JsonObject = dict[str, Any]
ArtifactKind = Literal["workflow", "wrapper"]
SourceRefInput = SourceRef | str
CapabilityRefInput = CapabilityRef | str


class DriftPolicy(StrEnum):
    """Policy for dependency drift that is detected but not proven unsafe."""

    BLOCK = "block"
    WARN = "warn"
    ALLOW = "allow"


class DiagnosticSeverity(StrEnum):
    """Severity level for dependency validation diagnostics."""

    ERROR = "error"
    WARNING = "warning"


class RequiredCapability(BaseModel):
    """Saved contract for one capability an artifact references."""

    ref: CapabilityRefInput
    kind: Literal["tool", "resource", "prompt", "node_spec", "reducer", "workflow"]
    input_schema_hash: str | None = None
    input_schema_snapshot: JsonObject | None = None
    output_schema_hash: str | None = None
    output_schema_snapshot: JsonObject | None = None
    observed_concrete_source: SourceRefInput | None = None
    observed_at_epoch_ms: int | None = Field(default=None, ge=0)

    @property
    def logical_source(self) -> str:
        """Compatibility accessor for callers migrating to `ref`."""
        return str(self.capability_ref().source)

    @property
    def capability_name(self) -> str:
        """Compatibility accessor for callers migrating to `ref`."""
        return self.capability_ref().name

    def capability_ref(self) -> CapabilityRef:
        """Return the typed ref even when constructed from JSON-compatible input."""
        return (
            self.ref
            if isinstance(self.ref, CapabilityRef)
            else CapabilityRef.parse(self.ref)
        )

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_ref_fields(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        if "ref" not in data:
            logical_source = data.pop("logical_source", None)
            capability_name = data.pop("capability_name", None)
            if isinstance(logical_source, str) and isinstance(capability_name, str):
                data["ref"] = f"{logical_source}.{capability_name}"
        return data


class AvailableCapability(BaseModel):
    """Current contract for one capability exposed by a bound source."""

    name: str
    kind: Literal["tool", "resource", "prompt", "node_spec", "reducer", "workflow"]
    input_schema_hash: str | None = None
    output_schema_hash: str | None = None


class AvailableSource(BaseModel):
    """Provider-neutral source snapshot used by artifact dependency validation."""

    id: str
    enabled: bool = True
    capabilities: dict[str, AvailableCapability] = Field(default_factory=dict)


class SourceBinding(BaseModel):
    """Deployment-time mapping from artifact logical source to concrete source."""

    logical_source: SourceRefInput
    concrete_source: SourceRefInput

    def logical_ref(self) -> SourceRef:
        """Return the typed logical source ref for runtime lookup code."""
        return (
            self.logical_source
            if isinstance(self.logical_source, SourceRef)
            else SourceRef.parse(self.logical_source)
        )

    def concrete_ref(self) -> SourceRef:
        """Return the typed concrete source ref for runtime lookup code."""
        return (
            self.concrete_source
            if isinstance(self.concrete_source, SourceRef)
            else SourceRef.parse(self.concrete_source)
        )


class DependencyDiagnostic(BaseModel):
    """Machine-readable reason a deployment is degraded or unrunnable."""

    severity: DiagnosticSeverity
    code: str
    logical_ref: str
    bound_source: str | None = None
    message: str
    repair_hint: str | None = None


class WorkflowArtifact(BaseModel):
    """Immutable saved workflow definition plus dependency contract snapshots."""

    id: str
    version: int = Field(ge=1)
    title: str
    kind: ArtifactKind = "workflow"
    description: str | None = None
    input_schema: JsonObject
    output_schema: JsonObject
    outcomes: tuple[str, ...]
    plan: JsonObject
    required_capabilities: (
        list[RequiredCapability] | dict[str, RequiredCapability | JsonObject]
    ) = Field(default_factory=list)
    workflow_dependencies: dict[str, int] = Field(default_factory=dict)
    created_from_catalog_version: str | None = None

    def required_capability_map(self) -> dict[str, RequiredCapability]:
        """Return required capabilities keyed by dot-joined capability ref."""
        return {
            str(capability.capability_ref()): capability
            for capability in self._required_capability_list()
        }

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_required_capabilities(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        required = data.get("required_capabilities")
        if not isinstance(required, dict):
            return data

        normalized: list[object] = []
        for raw_ref, raw_capability in required.items():
            if not isinstance(raw_capability, dict):
                normalized.append(raw_capability)
                continue
            capability_data = dict(raw_capability)
            capability_data.setdefault("ref", str(raw_ref))
            normalized.append(capability_data)
        data["required_capabilities"] = normalized
        return data

    @model_validator(mode="after")
    def _reject_duplicate_required_capabilities(self) -> WorkflowArtifact:
        self.required_capabilities = self._required_capability_list()
        refs = [
            str(capability.capability_ref())
            for capability in self.required_capabilities
        ]
        duplicates = {ref for ref in refs if refs.count(ref) > 1}
        if duplicates:
            raise ValueError(
                "duplicate required capability refs: " + ", ".join(sorted(duplicates))
            )
        return self

    def _required_capability_list(self) -> list[RequiredCapability]:
        if isinstance(self.required_capabilities, dict):
            return [
                RequiredCapability.model_validate(
                    {"ref": ref, **capability}
                    if isinstance(capability, dict)
                    else capability
                )
                for ref, capability in self.required_capabilities.items()
            ]
        return self.required_capabilities


class WorkflowDeployment(BaseModel):
    """One configured way to run an artifact version in an environment."""

    id: str
    artifact_id: str
    artifact_version: int = Field(ge=1)
    bindings: list[SourceBinding | dict[str, str]] | dict[str, str] = Field(
        default_factory=list
    )
    drift_policy: DriftPolicy = DriftPolicy.BLOCK

    def binding_map(self) -> dict[str, str]:
        """Return bindings keyed by dot-joined logical source ref."""
        return {
            str(binding.logical_ref()): str(binding.concrete_ref())
            for binding in self._binding_list()
        }

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_binding_map(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        bindings = data.get("bindings")
        if not isinstance(bindings, dict):
            return data

        data["bindings"] = [
            {"logical_source": logical, "concrete_source": concrete}
            for logical, concrete in bindings.items()
        ]
        return data

    @model_validator(mode="after")
    def _reject_duplicate_bindings(self) -> WorkflowDeployment:
        normalized = self._binding_list()
        self.bindings = [*normalized]
        logical_sources = [str(binding.logical_ref()) for binding in normalized]
        duplicates = {
            source for source in logical_sources if logical_sources.count(source) > 1
        }
        if duplicates:
            raise ValueError(
                "duplicate deployment source bindings: " + ", ".join(sorted(duplicates))
            )
        return self

    def _binding_list(self) -> list[SourceBinding]:
        if isinstance(self.bindings, dict):
            return [
                SourceBinding(logical_source=logical, concrete_source=concrete)
                for logical, concrete in self.bindings.items()
            ]
        return [
            binding
            if isinstance(binding, SourceBinding)
            else SourceBinding.model_validate(binding)
            for binding in self.bindings
        ]
