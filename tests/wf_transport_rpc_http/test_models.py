from __future__ import annotations

import pytest
from pydantic import ValidationError

from wf_transport_rpc_http.models import (
    InspectCapabilityParams,
    ListCapabilitiesParams,
    ReadRunTraceParams,
    StartRunParams,
    TraceRangeParams,
)


def test_trace_range_params_converts_to_api_trace_range() -> None:
    trace_range = TraceRangeParams(start=2, limit=5).to_api_trace_range()

    assert trace_range.start == 2
    assert trace_range.limit == 5


def test_trace_range_params_rejects_invalid_values() -> None:
    with pytest.raises(ValidationError):
        TraceRangeParams(start=-1, limit=5)

    with pytest.raises(ValidationError):
        TraceRangeParams(start=0, limit=0)

    with pytest.raises(ValidationError):
        TraceRangeParams(start=0, limit=101)


def test_capability_params_are_explicit_models() -> None:
    listed = ListCapabilitiesParams(query="echo", source_id="wf.std", limit=10)
    inspected = InspectCapabilityParams(qualified_name="wf.std.constant")

    assert listed.query == "echo"
    assert listed.source_id == "wf.std"
    assert listed.limit == 10
    assert inspected.qualified_name == "wf.std.constant"


def test_run_params_are_explicit_models() -> None:
    started = StartRunParams(
        deployment_id="demo.default",
        workflow_input={"message": "hello"},
        trace_range=TraceRangeParams(start=0, limit=3),
    )
    trace = ReadRunTraceParams(
        run_id="run_demo",
        trace_range=TraceRangeParams(start=0, limit=1),
    )

    assert started.deployment_id == "demo.default"
    assert started.workflow_input["message"] == "hello"
    assert started.trace_range is not None
    assert trace.run_id == "run_demo"
    assert trace.trace_range.limit == 1
