from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from wf_artifacts import RequiredCapability, WorkflowArtifact, WorkflowDeployment
from wf_authoring import AsyncRegistryHandler, NodeSpec, build_async_registry
from wf_core.runtime.ops.merges import ReducerDefinition
from wf_platform import CapabilityRef, CapabilitySource


@dataclass(frozen=True, slots=True)
class RuntimeDependencies:
    """Executable dependencies resolved for one workflow run."""

    node_specs: dict[str, NodeSpec[Any, Any]]
    node_name_bindings: dict[str, str]
    node_registry: dict[str, AsyncRegistryHandler]
    reducers: dict[str, ReducerDefinition]


def resolve_runtime_dependencies(
    *,
    artifact: WorkflowArtifact,
    deployment: WorkflowDeployment | None,
    sources: dict[str, CapabilitySource],
    plan_node_names: list[str],
) -> RuntimeDependencies:
    """Resolve source-owned specs and reducers into runtime callables.

    Node names in stored plans are still concrete today, so node specs resolve
    by exact plan names. Reducers are already logical artifact dependencies, so
    they resolve through deployment bindings and are registered under the
    logical reducer name used by the workflow state schema.
    """
    node_specs: dict[str, NodeSpec[Any, Any]] = {}
    node_name_bindings: dict[str, str] = {}
    for node_name in dict.fromkeys(plan_node_names):
        concrete_name, spec = _resolve_node_spec(
            node_name=node_name,
            deployment=deployment,
            sources=sources,
        )
        node_name_bindings[node_name] = concrete_name
        node_specs[concrete_name] = spec
    reducers = _resolve_reducers(
        required_capabilities=artifact.required_capability_map(),
        deployment=deployment,
        sources=sources,
    )
    return RuntimeDependencies(
        node_specs=node_specs,
        node_name_bindings=node_name_bindings,
        node_registry=build_async_registry(*node_specs.values()),
        reducers=reducers,
    )


def _resolve_node_spec(
    *,
    node_name: str,
    deployment: WorkflowDeployment | None,
    sources: dict[str, CapabilitySource],
) -> tuple[str, NodeSpec[Any, Any]]:
    concrete = _find_node_spec(node_name, sources)
    if concrete is not None:
        return node_name, concrete

    if deployment is not None:
        for bound_name in _bound_node_names(node_name, deployment.binding_map()):
            concrete = _find_node_spec(bound_name, sources)
            if concrete is not None:
                return bound_name, concrete

    raise KeyError(f"unknown node spec {node_name!r}")


def _bound_node_names(
    node_name: str,
    bindings: dict[str, str],
) -> tuple[str, ...]:
    """Return concrete names made by replacing known logical source prefixes.

    CapabilityRef parses by splitting on the last dot, which is correct for
    simple tool names but wrong for local names that also contain dots
    (`demo.foo.bar` with logical source `demo`). Runtime binding is source-aware:
    deployment bindings define the allowed source prefixes, and everything after
    the matched prefix remains the local capability name.
    """
    candidates: list[str] = []
    for logical_source, concrete_source in sorted(
        bindings.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        prefix = f"{logical_source}."
        if node_name.startswith(prefix):
            candidates.append(f"{concrete_source}.{node_name[len(prefix) :]}")
    return tuple(candidates)


def _find_node_spec(
    node_name: str,
    sources: dict[str, CapabilitySource],
) -> NodeSpec[Any, Any] | None:
    for source in sources.values():
        spec = source.capabilities.node_specs.get(node_name)
        if spec is not None:
            return spec
    return None


def _resolve_reducers(
    *,
    required_capabilities: dict[str, RequiredCapability],
    deployment: WorkflowDeployment | None,
    sources: dict[str, CapabilitySource],
) -> dict[str, ReducerDefinition]:
    reducers: dict[str, ReducerDefinition] = {}
    bindings = deployment.binding_map() if deployment is not None else {}

    for logical_ref, required in required_capabilities.items():
        if required.kind != "reducer":
            continue
        source = _find_source_for_reducer(
            logical_source=required.logical_source,
            bindings=bindings,
            sources=sources,
        )
        if source is None:
            continue
        definition = _find_reducer_definition(
            source=source,
            capability_name=required.capability_name,
        )
        if definition is not None:
            reducers[logical_ref] = definition
    return reducers


def _find_source_for_reducer(
    *,
    logical_source: str,
    bindings: dict[str, str],
    sources: dict[str, CapabilitySource],
) -> CapabilitySource | None:
    """Find the source that owns a reducer for a logical source.

    Platform sources resolve by exact ``logical_source`` without a deployment
    binding.  External sources require a binding entry.
    """
    platform_source = sources.get(logical_source)
    if platform_source is not None and platform_source.policy.platform:
        return platform_source

    bound_source_id = bindings.get(logical_source)
    if bound_source_id is None:
        return None
    return sources.get(bound_source_id)


def _find_reducer_definition(
    *,
    source: CapabilitySource,
    capability_name: str,
) -> ReducerDefinition | None:
    for reducer_name, definition in source.capabilities.reducer_definitions.items():
        try:
            reducer_ref = CapabilityRef.parse(reducer_name)
        except ValueError:
            continue
        if reducer_ref.name == capability_name:
            return definition
    return None
