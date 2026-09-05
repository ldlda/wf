from __future__ import annotations

from typing import Any, cast

from wf_client.capabilities import CapabilityResult, RemoteCapability
from wf_client.deployments import Deployment, DeploymentValidation
from wf_client.protocols import WorkflowClientPort
from wf_client.runs import Run, TracePage
from wf_client.workflows import (
    ArtifactRef,
    WorkflowDiagnostic,
    WorkflowValidation,
)
from wf_core import ValidationReport
from wf_platform import CapabilityRef


class _Port:
    """A port that records accidental representation-time remote operations."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __getattr__(self, name: str) -> Any:
        async def operation(**params: Any) -> object:
            self.calls.append((name, params))
            return {}

        return operation


def _port() -> _Port:
    return _Port()


def test_capability_html_repr_is_bounded_and_does_not_call_port() -> None:
    port = _port()
    remote = RemoteCapability(
        _port=cast(WorkflowClientPort, port),
        ref=CapabilityRef.parse("app.default.search"),
        qualified_name="app.default.search",
        description="Search things <carefully>",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"items": {"type": "array"}}},
        outcomes=("ok",),
        is_async=False,
    )

    rendered = remote._repr_html_()

    assert "app.default.search" in rendered
    assert "input schema" in rendered.lower()
    assert "&lt;carefully&gt;" in rendered
    assert port.calls == []


def test_rich_representations_bound_large_values_and_redact_secret_like_fields() -> (
    None
):
    port = _port()
    result = CapabilityResult(
        outcome="ok",
        output={"token": "do-not-show", "items": ["x" * 400] * 20},
        diagnostics=(),
    )
    run = Run(
        _port=cast(WorkflowClientPort, port),
        run_id="run-1",
        deployment_id="deployment-1",
        status="completed",
        outcome="ok",
        output=result.output,
        interrupt=None,
        diagnostics=(),
        trace_count=1000,
        max_steps=10_000,
        steps_executed=3,
        steps_remaining=9_997,
    )

    rendered = repr(run)
    html = run._repr_html_()

    assert len(rendered) <= 1_201
    assert len(html) <= 2_500
    assert "do-not-show" not in rendered
    assert "do-not-show" not in html
    assert "1000 frames" in rendered
    assert port.calls == []


def test_repr_redacts_only_exact_sensitive_keys_in_snake_and_camel_case() -> None:
    result = CapabilityResult(
        outcome="ok",
        output={
            "apiKey": "hide-me",
            "accessToken": "hide-me-too",
            "setCookie": "hide-me-three",
            "tokenCount": 3,
            "authorizationStatus": "ok",
            "secretary": "safe",
        },
        diagnostics=(),
    )

    rendered = repr(result)

    assert "hide-me" not in rendered
    assert "hide-me-too" not in rendered
    assert "hide-me-three" not in rendered
    assert '"tokenCount": 3' in rendered
    assert '"authorizationStatus": "ok"' in rendered
    assert '"secretary": "safe"' in rendered


def test_repr_does_not_materialize_an_unbounded_iterable() -> None:
    class ExplodingIterable:
        def __iter__(self):
            for index in range(10_000):
                if index > 8:
                    raise AssertionError("repr consumed too many values")
                yield index

    result = CapabilityResult("ok", {"values": ExplodingIterable()}, ())

    rendered = repr(result)

    assert "more items" in rendered


def test_all_rich_objects_render_without_port_access() -> None:
    raw_port = _port()
    port = cast(WorkflowClientPort, raw_port)
    diagnostic = WorkflowDiagnostic("error", "bad", "state.x", "broken")
    local = ValidationReport()
    objects = [
        ArtifactRef("artifact", 1),
        diagnostic,
        WorkflowValidation(local, "valid", (diagnostic,)),
        CapabilityResult("ok", {"value": 1}, ()),
        DeploymentValidation("deployment", "artifact", 1, "runnable", ()),
        TracePage(0, 25, (), False, 0),
    ]

    for value in objects:
        assert repr(value)
        assert value._repr_html_()
    assert repr(
        Deployment.from_payload(
            port,
            {
                "id": "deployment",
                "artifact_id": "artifact",
                "artifact_version": 1,
                "bindings": [],
                "drift_policy": "block",
            },
        )
    )
    assert raw_port.calls == []
