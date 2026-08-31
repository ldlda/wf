"""The public entry point for transport-independent workflow clients."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from wf_platform import CapabilityRef, Page, SourceRef
from wf_transport_rpc_http import RpcWorkflowApiClient

from ._http_port import PublicErrorWorkflowClientPort
from ._identity import require_response_identity
from .authoring import EditableWorkflow
from .capabilities import CapabilitySummary, RemoteCapability
from .codec import (
    decode_capabilities_page,
    decode_capability_inspect,
    decode_workflow_artifact,
)
from .errors import InvalidResponse
from .protocols import WorkflowClientPort
from .workflows import WorkflowArtifact

if TYPE_CHECKING:
    from .deployments import Deployment
    from .runs import Run


def _capability_ref(qualified_name: str, source_id: str) -> CapabilityRef:
    """Build a ref by removing the exact source prefix, preserving dotted keys."""
    prefix = f"{source_id}."
    if not qualified_name.startswith(prefix):
        raise InvalidResponse(
            operation="workflow.capabilities.inspect",
            details=(
                f"qualified name {qualified_name!r} does not belong to "
                f"source {source_id!r}"
            ),
        )
    try:
        return CapabilityRef(
            source=SourceRef.parse(source_id),
            name=qualified_name.removeprefix(prefix),
        )
    except ValueError as exc:
        raise InvalidResponse(
            operation="workflow.capabilities.inspect",
            details=f"invalid capability reference: {exc}",
        ) from exc


def _summary_from_wire(row: object) -> CapabilitySummary:
    """Project one wire discovery row into an attribute-bearing value object."""
    data = dict(row) if isinstance(row, dict) else {}
    return CapabilitySummary(
        qualified_name=data["name"],
        source_id=data["source_id"],
        kind=data["kind"],
        description=data["description"],
        outcomes=tuple(data["outcomes"]),
        is_async=data["is_async"],
        input_fields=tuple(data["input_fields"]),
        output_fields=tuple(data["output_fields"]),
        artifact_id=data.get("artifact_id"),
        version=data.get("version"),
        title=data.get("title"),
    )


@dataclass(frozen=True, slots=True)
class App:
    """Connected workflow service facade; all remote methods are asynchronous."""

    _port: WorkflowClientPort = field(repr=False)
    endpoint: str

    @classmethod
    def from_http_jsonrpc(
        cls,
        url: str,
        *,
        timeout_seconds: float = 30.0,
    ) -> App:
        """Configure a lazy HTTP JSON-RPC connection without performing I/O."""
        return cls(
            _port=PublicErrorWorkflowClientPort(
                RpcWorkflowApiClient(
                    url=url,
                    timeout_seconds=timeout_seconds,
                )
            ),
            endpoint=url,
        )

    @classmethod
    def _from_port(cls, port: WorkflowClientPort) -> App:
        """Construct an app over an in-memory/test port."""
        return cls(_port=port, endpoint="in-process")

    async def capability(self, name: str) -> RemoteCapability:
        """Inspect and reconstruct one callable remote capability."""
        wire = decode_capability_inspect(
            await self._port.inspect_capability(qualified_name=name)
        )
        qualified_name = wire["name"]
        if qualified_name != name:
            raise InvalidResponse(
                operation="workflow.capabilities.inspect",
                details=(
                    f"inspected capability {qualified_name!r} does not match "
                    f"requested {name!r}"
                ),
            )
        source_id = wire["source_id"]
        return RemoteCapability(
            _port=self._port,
            ref=_capability_ref(qualified_name, source_id),
            qualified_name=qualified_name,
            description=wire["description"],
            input_schema=dict(wire["input_schema"]),
            output_schema=dict(wire["output_schema"]),
            outcomes=tuple(wire["outcomes"]),
            is_async=wire["is_async"],
            _kind=wire["kind"],
        )

    async def capabilities(
        self,
        *,
        query: str | None = None,
        source_id: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> Page[CapabilitySummary]:
        """List planner-visible capabilities as immutable rich rows."""
        wire = decode_capabilities_page(
            await self._port.list_capabilities(
                query=query,
                source_id=source_id,
                cursor=cursor,
                limit=limit,
            )
        )
        return Page(
            items=tuple(_summary_from_wire(row) for row in wire["capabilities"]),
            next_cursor=wire["next_cursor"],
            total=wire["total"],
        )

    def new_workflow(
        self,
        name: str,
        *,
        input_schema: Any,
        state_schema: Any,
        output_schema: Any,
        outcomes: Sequence[str] = ("ok",),
    ) -> EditableWorkflow:
        """Construct a local builder; remote operations remain opt-in/async."""
        return EditableWorkflow(
            _port=self._port,
            name=name,
            input_schema=input_schema,
            state_schema=state_schema,
            output_schema=output_schema,
            outcomes=outcomes,
        )

    async def workflow(self, artifact_id: str, *, version: int) -> WorkflowArtifact:
        """Inspect and reconstruct one exact immutable workflow artifact version."""
        artifact, workflow = decode_workflow_artifact(
            await self._port.inspect_artifact(
                artifact_id=artifact_id,
                version=version,
            )
        )
        require_response_identity(
            operation="workflow.artifacts.inspect",
            actual={"artifact_id": artifact.id, "version": artifact.version},
            expected={"artifact_id": artifact_id, "version": version},
        )
        return WorkflowArtifact(self._port, artifact, workflow)

    async def edit_workflow(
        self,
        artifact_id: str,
        *,
        version: int,
    ) -> EditableWorkflow:
        """Inspect an exact artifact version and seed an editable builder."""
        return (await self.workflow(artifact_id, version=version)).edit()

    async def deployment(self, deployment_id: str) -> Deployment:
        """Inspect and reconstruct one immutable deployment snapshot."""
        from .deployments import Deployment

        deployment = Deployment.from_payload(
            self._port,
            await self._port.inspect_deployment(deployment_id=deployment_id),
        )
        if deployment.deployment_id != deployment_id:
            raise InvalidResponse(
                operation="workflow.deployments.inspect",
                details=(
                    f"inspected deployment {deployment.deployment_id!r} does not "
                    f"match requested {deployment_id!r}"
                ),
            )
        return deployment

    async def run(self, run_id: str) -> Run:
        """Inspect and reconstruct one immutable durable run snapshot."""
        from .runs import Run

        return Run.from_payload(
            self._port,
            await self._port.inspect_run(run_id=run_id),
            expected_run_id=run_id,
            operation="workflow.runs.inspect",
        )
