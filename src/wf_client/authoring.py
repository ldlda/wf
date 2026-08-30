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
    _permissive_node_defs: set[str] = field(
        default_factory=set, repr=False, kw_only=True
    )

    @classmethod
    def from_artifact(cls, artifact: WorkflowArtifact) -> EditableWorkflow:
        """Copy every canonical graph field from an immutable artifact snapshot."""
        builder = WorkflowBuilder.from_workflow(artifact.workflow)
        permissive_node_defs = _seed_remote_node_defs(builder, artifact)
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
            _permissive_node_defs=permissive_node_defs,
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

    def use_contract(self, node_def: NodeDef, **kwargs: Any) -> NodeUse:
        """Upgrade an artifact placeholder before normal duplicate checks."""
        if node_def.name in self._permissive_node_defs:
            self.seeded_node_defs.pop(node_def.name, None)
            self._permissive_node_defs.remove(node_def.name)
        return super().use_contract(node_def, **kwargs)

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
) -> set[str]:
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
    permissive_names: set[str] = set()
    for requirement in artifact.required_capabilities:
        if requirement.kind != "node_spec":
            continue
        name = str(requirement.capability_ref())
        node_uses = [
            node
            for node in artifact.workflow.nodes
            if isinstance(node, NodeUse) and node.node == name
        ]
        input_fields = {
            field
            for node in node_uses
            for binding in node.input
            if (field := _binding_root_field(binding.target)) is not None
        }
        output_fields = {
            field
            for node in node_uses
            for binding in node.output
            if (field := _binding_root_field(binding.source)) is not None
        }
        input_schema = _snapshot_or_permissive_schema(
            requirement.input_schema_snapshot,
            input_fields,
        )
        output_schema = _snapshot_or_permissive_schema(
            requirement.output_schema_snapshot,
            output_fields,
        )
        if not isinstance(requirement.input_schema_snapshot, dict) or not isinstance(
            requirement.output_schema_snapshot, dict
        ):
            permissive_names.add(name)
        builder.seeded_node_defs.setdefault(
            name,
            NodeDef(
                name=name,
                input_schema=SchemaRef.model_validate(input_schema),
                output_schema=SchemaRef.model_validate(output_schema),
                outcomes=outcomes_by_node.get(name, ["ok"]),
            ),
        )
    return permissive_names


def _binding_root_field(path: object) -> str | None:
    """Return a local binding's first field, excluding whole-payload ``.``."""
    parts = getattr(path, "parts", ())
    if not parts:
        return None
    return parts[0]


def _snapshot_or_permissive_schema(
    snapshot: object,
    fields: set[str],
) -> dict[str, Any]:
    """Use a saved snapshot or an unconstrained schema for its used fields.

    A missing server snapshot carries no type information. Declaring only the
    fields already referenced by graph bindings lets local structural checks
    proceed without inventing validation constraints for remote data.
    """
    if isinstance(snapshot, dict):
        return snapshot
    return {
        "type": "object",
        "properties": {field: {} for field in sorted(fields)},
    }
