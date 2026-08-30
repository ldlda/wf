"""Transport-independent workflow client primitives."""

from wf_platform import CapabilityRef, Page

from .app import App
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
    decode_run_result,
    decode_trace_result,
    decode_workflow_artifact,
)
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

__all__ = [
    "ArtifactNotFound",
    "ArtifactVersionConflict",
    "App",
    "CapabilityNotFound",
    "CapabilityRef",
    "CapabilityResult",
    "CapabilitySummary",
    "DecodedRunResult",
    "DecodedTracePage",
    "DeploymentNotRunnable",
    "DeploymentRequired",
    "InvalidResponse",
    "Page",
    "ProtocolError",
    "RemoteCapability",
    "RevisionConflict",
    "TransportError",
    "ValidationFailed",
    "WorkflowClientError",
    "WorkflowClientPort",
    "decode_capabilities_page",
    "decode_capability_call",
    "decode_capability_diagnostics",
    "decode_capability_inspect",
    "decode_dependency_diagnostics",
    "decode_deployment",
    "decode_run_result",
    "decode_trace_result",
    "decode_workflow_artifact",
]
