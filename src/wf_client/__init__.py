"""Transport-independent workflow client primitives."""

from wf_platform import CapabilityRef, Page

from .app import App
from .authoring import EditableWorkflow
from .capabilities import CapabilityResult, CapabilitySummary, RemoteCapability
from .codec import (
    DecodedRunResult,
    DecodedTracePage,
    decode_capabilities_page,
    decode_capability_call,
    decode_capability_diagnostics,
    decode_capability_inspect,
    decode_dependency_diagnostics,
    decode_deployment,
    decode_deployment_validation,
    decode_deployments,
    decode_run_result,
    decode_trace_result,
    decode_validate_artifact_plan,
    decode_workflow_artifact,
)
from .deployments import Deployment, DeploymentValidation
from .errors import (
    ArtifactNotFound,
    ArtifactVersionConflict,
    CapabilityNotFound,
    DeploymentNotRunnable,
    DeploymentRequired,
    InvalidResponse,
    ProtocolError,
    RevisionConflict,
    TransportError,
    ValidationFailed,
    WorkflowClientError,
)
from .protocols import WorkflowClientPort
from .runs import Run, TracePage
from .workflows import (
    ArtifactRef,
    Diagnostic,
    WorkflowArtifact,
    WorkflowDiagnostic,
    WorkflowValidation,
)

__all__ = [
    "ArtifactNotFound",
    "ArtifactVersionConflict",
    "App",
    "ArtifactRef",
    "CapabilityNotFound",
    "CapabilityRef",
    "CapabilityResult",
    "CapabilitySummary",
    "DecodedRunResult",
    "DecodedTracePage",
    "Diagnostic",
    "DeploymentNotRunnable",
    "DeploymentRequired",
    "Deployment",
    "DeploymentValidation",
    "InvalidResponse",
    "Page",
    "ProtocolError",
    "RemoteCapability",
    "Run",
    "RevisionConflict",
    "TransportError",
    "ValidationFailed",
    "WorkflowClientError",
    "WorkflowClientPort",
    "EditableWorkflow",
    "WorkflowArtifact",
    "WorkflowDiagnostic",
    "WorkflowValidation",
    "TracePage",
    "decode_capabilities_page",
    "decode_capability_call",
    "decode_capability_diagnostics",
    "decode_capability_inspect",
    "decode_dependency_diagnostics",
    "decode_deployment_validation",
    "decode_deployments",
    "decode_deployment",
    "decode_run_result",
    "decode_trace_result",
    "decode_validate_artifact_plan",
    "decode_workflow_artifact",
]
