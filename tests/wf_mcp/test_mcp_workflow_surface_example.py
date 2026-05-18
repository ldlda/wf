from __future__ import annotations

import asyncio

from examples.mcp_workflow_surface import (
    build_echo_draft,
    create_and_run_echo_deployment,
    prepare_demo_service,
)


def test_mcp_workflow_surface_example_discovers_ok_and_error_outcomes(
    tmp_path,
) -> None:
    service = asyncio.run(prepare_demo_service(tmp_path))

    source = service.inspect_source("demo.personal")
    node_spec = source["capabilities"]["node_spec_details"][0]

    assert node_spec["name"] == "demo.personal.echo_tool"
    assert node_spec["outcomes"] == ["ok", "error"]


def test_mcp_workflow_surface_example_wires_naive_error_outcome() -> None:
    draft = build_echo_draft()

    assert draft["routes"]["echo"]["ok"] == "__end__"
    assert draft["routes"]["echo"]["error"] == "tool_error"
    assert draft["steps"]["tool_error"]["use"] == "wf.std.runtime_error"


def test_mcp_workflow_surface_example_runs_happy_path(tmp_path) -> None:
    payload = asyncio.run(create_and_run_echo_deployment(tmp_path, text="hello"))

    assert payload["status"] == "completed"
    assert payload["output"]["echoed"] == "hello"
    assert payload["diagnostics"] == []
