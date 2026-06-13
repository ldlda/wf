"""Regression: platform sources resolve reducers without deployment bindings."""

from __future__ import annotations

from unittest.mock import MagicMock

from wf_api.runtime_dependencies import resolve_runtime_dependencies
from wf_artifacts import RequiredCapability, WorkflowArtifact
from wf_core.runtime.ops.merges import ReducerDefinition, ReducerSpec, replace_reducer
from wf_platform import (
    CapabilityBuckets,
    CapabilitySource,
    SourcePolicy,
    SourceVisibility,
)


def _platform_source_with_reducer() -> CapabilitySource:
    spec = ReducerSpec(name="wf.std.replace", description="Replace value.")
    definition = ReducerDefinition(spec=spec, fn=replace_reducer)
    return CapabilitySource(
        id="wf.std",
        kind="system",
        capabilities=CapabilityBuckets(
            reducers={"wf.std.replace": spec},
            reducer_definitions={"wf.std.replace": definition},
        ),
        visibility=SourceVisibility(planner=True),
        policy=SourcePolicy(platform=True, binding_required=False),
    )


def _non_platform_unbound_source_with_reducer() -> CapabilitySource:
    spec = ReducerSpec(name="custom.replace", description="Replace value.")
    definition = ReducerDefinition(spec=spec, fn=replace_reducer)
    return CapabilitySource(
        id="custom",
        kind="system",
        capabilities=CapabilityBuckets(
            reducers={"custom.replace": spec},
            reducer_definitions={"custom.replace": definition},
        ),
        visibility=SourceVisibility(planner=True),
        policy=SourcePolicy(platform=False, binding_required=False),
    )


def _make_artifact_with_reducer(capability_name: str) -> WorkflowArtifact:
    source, name = capability_name.rsplit(".", 1)
    artifact = MagicMock(spec=WorkflowArtifact)
    artifact.required_capability_map.return_value = {
        capability_name: RequiredCapability(
            ref=f"{source}.{name}",
            kind="reducer",
        ),
    }
    return artifact


def test_platform_source_reducer_resolves_with_empty_bindings() -> None:
    artifact = _make_artifact_with_reducer("wf.std.replace")
    reducers = resolve_runtime_dependencies(
        artifact=artifact,
        deployment=None,
        sources={"wf.std": _platform_source_with_reducer()},
        plan_node_names=[],
    ).reducers

    assert "wf.std.replace" in reducers
    assert reducers["wf.std.replace"].spec.name == "wf.std.replace"


def test_platform_source_reducer_resolves_with_no_matching_binding() -> None:
    from wf_artifacts import WorkflowDeployment

    artifact = _make_artifact_with_reducer("wf.std.replace")
    deployment = MagicMock(spec=WorkflowDeployment)
    deployment.binding_map.return_value = {"external_source": "demo.personal"}
    reducers = resolve_runtime_dependencies(
        artifact=artifact,
        deployment=deployment,
        sources={"wf.std": _platform_source_with_reducer()},
        plan_node_names=[],
    ).reducers

    assert "wf.std.replace" in reducers


def test_non_platform_unbound_reducer_does_not_resolve_without_binding() -> None:
    artifact = _make_artifact_with_reducer("custom.replace")
    reducers = resolve_runtime_dependencies(
        artifact=artifact,
        deployment=None,
        sources={"custom": _non_platform_unbound_source_with_reducer()},
        plan_node_names=[],
    ).reducers

    assert reducers == {}
