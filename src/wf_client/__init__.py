"""Transport-independent workflow client primitives."""

from .codec import (
    DecodedRunResult,
    DecodedTracePage,
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
    "CapabilityNotFound",
    "DecodedRunResult",
    "DecodedTracePage",
    "DeploymentNotRunnable",
    "DeploymentRequired",
    "InvalidResponse",
    "ProtocolError",
    "RevisionConflict",
    "TransportError",
    "ValidationFailed",
    "WorkflowClientError",
    "WorkflowClientPort",
    "decode_dependency_diagnostics",
    "decode_deployment",
    "decode_run_result",
    "decode_trace_result",
    "decode_workflow_artifact",
]
