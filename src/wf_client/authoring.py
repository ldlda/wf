"""Editable workflow authoring over the transport-independent builder."""

from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, overload

from wf_authoring import WorkflowBuilder
from wf_authoring.builder.mapping import OutputBindingArg, StepInputBindingArg
from wf_authoring.nodes import NodeSpec
from wf_core import (
    NodeDef,
    NodeUse,
    SchemaRef,
    SubgraphNode,
    ValidationReport,
    Workflow,
)

from .capabilities import RemoteCapability
from .codec import decode_validate_artifact_plan, decode_workflow_artifact
from .protocols import WorkflowClientPort
from .workflows import (
    ArtifactRef,
    WorkflowArtifact,
    WorkflowDiagnostic,
    WorkflowValidation,
)


@dataclass(slots=True)
class EditableWorkflow(WorkflowBuilder):
    """A mutable ``WorkflowBuilder`` carrying the client port used to save it."""

    _port: WorkflowClientPort = field(repr=False, kw_only=True)
    based_on: ArtifactRef | None = field(default=None, kw_only=True)
    artifact_title: str | None = field(default=None, kw_only=True)
    artifact_description: str | None = field(default=None, kw_only=True)
    _source_plan: dict[str, Any] | None = field(default=None, repr=False, kw_only=True)
    _source_workflow: Workflow | None = field(
        default=None, repr=False, kw_only=True
    )

    @classmethod
    def from_artifact(cls, artifact: WorkflowArtifact) -> EditableWorkflow:
        """Copy every canonical graph field from an immutable artifact snapshot."""
        builder = WorkflowBuilder.from_workflow(artifact.workflow)
        _seed_remote_node_defs(builder, artifact)
        return cls(
            _port=artifact._port,
            based_on=artifact.ref,
            artifact_title=artifact.title,
            artifact_description=artifact.description,
            name=builder.name,
            input_schema=builder.input_schema,
            state_schema=builder.state_schema,
            output_schema=builder.output_schema,
            outcomes=builder.outcomes,
            start=builder.start,
            reducers=builder.reducers,
            node_specs=dict(builder.node_specs),
            nodes=builder.nodes,
            edges=builder.edges,
            workflow_output=builder.workflow_output,
            seeded_node_defs=builder.seeded_node_defs,
            prepared_subgraphs=builder.prepared_subgraphs,
            _source_plan=deepcopy(artifact.artifact.plan),
            _source_workflow=builder._build_workflow(start=builder.start or ""),
        )

    @overload
    def use(
        self,
        spec: NodeSpec[Any, Any],
        *,
        id: str | None = None,
        input: Sequence[StepInputBindingArg] | None = None,
        output: Sequence[OutputBindingArg] | None = None,
        desc: str | None = None,
    ) -> NodeUse: ...

    @overload
    def use(
        self,
        spec: RemoteCapability,
        *,
        id: str | None = None,
        input: Sequence[StepInputBindingArg] | None = None,
        output: Sequence[OutputBindingArg] | None = None,
        desc: str | None = None,
    ) -> NodeUse: ...

    def use(
        self,
        spec: NodeSpec[Any, Any] | RemoteCapability,
        **kwargs: Any,
    ) -> NodeUse:
        if isinstance(spec, RemoteCapability):
            return self.use_contract(spec.node_def(), **kwargs)
        return super().use(spec, **kwargs)

    def subgraph(
        self,
        workflow: WorkflowArtifact,
        *,
        id: str | None = None,
        input: Sequence[StepInputBindingArg] | None = None,
        output: Sequence[OutputBindingArg] | None = None,
        desc: str | None = None,
    ) -> SubgraphNode:
        """Add a native subgraph pinned to an immutable artifact version."""
        return super().subgraph(
            workflow=workflow.workflow,
            workflow_ref={
                "artifact_id": workflow.ref.artifact_id,
                "version": workflow.ref.version,
            },
            id=id,
            input=input,
            output=output,
            desc=desc,
        )

    def validate_local(self) -> ValidationReport:
        """Validate graph structure locally without touching the transport."""
        return self.validate_structure()

    def _plan(self) -> tuple[Workflow, dict[str, Any]]:
        workflow = self.compile()
        if (
            self._source_plan is not None
            and self._source_workflow is not None
            and workflow.model_dump(mode="json", by_alias=True)
            == self._source_workflow.model_dump(mode="json", by_alias=True)
        ):
            # Pydantic canonical models add omitted defaults during a round trip
            # (for example ``required=[]``). Keep an untouched artifact's raw
            # plan byte-for-byte structural equivalent until it is edited.
            return workflow, deepcopy(self._source_plan)
        plan = workflow.model_dump(mode="json", by_alias=True)
        # Node definitions are local execution metadata, not part of the raw
        # persisted artifact plan; the server inventories these from node refs.
        plan.pop("node_defs", None)
        return workflow, plan

    async def validate(self) -> WorkflowValidation:
        local = self.validate_local()
        if not local.ok:
            return WorkflowValidation(local, "not_run", ())

        _workflow, plan = self._plan()
        wire = decode_validate_artifact_plan(
            await self._port.validate_artifact_plan(
                plan=plan,
                outcomes=tuple(self.outcomes),
            )
        )
        diagnostics = tuple(
            WorkflowDiagnostic(
                severity=item["severity"],
                code=item["code"],
                path=item["path"],
                message=item["message"],
                repair_hint=item["repair_hint"],
            )
            for item in wire["diagnostics"]
        )
        return WorkflowValidation(local, wire["status"], diagnostics)

    async def save(
        self,
        *,
        artifact_id: str | None = None,
        version: int,
        title: str | None = None,
        description: str | None = None,
    ) -> WorkflowArtifact:
        validation = await self.validate()
        validation.raise_for_errors()
        _workflow, plan = self._plan()
        saved_id = artifact_id or (self.based_on.artifact_id if self.based_on else self.name)
        saved_title = title if title is not None else self.artifact_title or self.name
        saved_description = (
            description if description is not None else self.artifact_description
        )
        await self._port.create_artifact_from_plan(
            artifact_id=saved_id,
            version=version,
            title=saved_title,
            plan=plan,
            outcomes=tuple(self.outcomes),
            description=saved_description,
        )
        # The acknowledgement is only an identity signal. Inspecting the exact
        # requested version ensures server normalization is retained losslessly.
        inspected = await self._port.inspect_artifact(
            artifact_id=saved_id,
            version=version,
        )
        artifact, workflow = decode_workflow_artifact(inspected)
        return WorkflowArtifact(self._port, artifact, workflow)


def _seed_remote_node_defs(
    builder: WorkflowBuilder,
    artifact: WorkflowArtifact,
) -> None:
    """Restore remote node contracts retained as artifact dependency snapshots."""
    node_name_by_step_id = {
        node.id: node.node
        for node in artifact.workflow.nodes
        if isinstance(node, NodeUse)
    }
    outcomes_by_node: dict[str, list[str]] = {}
    for edge in artifact.workflow.edges:
        node_name = node_name_by_step_id.get(edge.from_)
        if node_name is not None:
            outcomes_by_node.setdefault(node_name, []).append(edge.outcome)
    for requirement in artifact.required_capabilities:
        if requirement.kind != "node_spec":
            continue
        input_schema = requirement.input_schema_snapshot
        output_schema = requirement.output_schema_snapshot
        if not isinstance(input_schema, dict) or not isinstance(output_schema, dict):
            continue
        name = str(requirement.capability_ref())
        builder.seeded_node_defs.setdefault(
            name,
            NodeDef(
                name=name,
                input_schema=SchemaRef.model_validate(input_schema),
                output_schema=SchemaRef.model_validate(output_schema),
                outcomes=outcomes_by_node.get(name, ["ok"]),
            ),
        )
