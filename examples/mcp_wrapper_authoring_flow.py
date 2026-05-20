from __future__ import annotations

from pathlib import Path
from typing import Any

from wf_artifacts import WorkflowDeployment
from wf_mcp.workflow_surface import WorkflowSurfaceHandlers

from mcp_workflow_surface import prepare_demo_service


async def author_echo_wrapper_from_capability(root: Path) -> dict[str, Any]:
    """Author, save, deploy, and run one wrapper from capability hints.

    This mirrors the intended MCP client flow:
    inspect one capability, create a patchable draft workspace from the returned
    wrapper_hints, validate/save that workspace as a wrapper artifact, then test
    the saved wrapper through `call_capability`.
    """
    service = await prepare_demo_service(root)
    handlers = WorkflowSurfaceHandlers(service)

    inspected = await handlers.inspect_capability(
        qualified_name="demo.personal.echo_tool"
    )
    workspace = await handlers.create_draft_workspace_from_capability(
        workspace_id="echo_wrapper_draft",
        capability_name="demo.personal.echo_tool",
        name="echo_wrapper",
        title="Echo Wrapper Draft",
    )
    created = await handlers.create_wrapper_from_workspace(
        workspace_id="echo_wrapper_draft",
        artifact_id="echo_wrapper",
        version=1,
        title="Echo Wrapper",
        outcomes=("ok", "error"),
        source_bindings={"demo": "demo.personal"},
    )

    assert service.artifact_store is not None
    service.artifact_store.save_deployment(
        WorkflowDeployment(
            id="echo_wrapper.personal",
            artifact_id="echo_wrapper",
            artifact_version=1,
            bindings=[
                {"logical_source": "demo", "concrete_source": "demo.personal"},
                {"logical_source": "wf.std", "concrete_source": "wf.std"},
            ],
        )
    )
    called = await handlers.call_capability(
        qualified_name="workflow.echo_wrapper.v1",
        payload={"text": "hello"},
        deployment_id="echo_wrapper.personal",
    )
    return {
        "inspected_hints": inspected["wrapper_hints"],
        "workspace": workspace,
        "created": created,
        "called": called,
    }


async def _amain() -> None:
    root = Path("test-artifacts") / "examples" / "mcp_wrapper_authoring_flow"
    payload = await author_echo_wrapper_from_capability(root)
    print(payload["created"]["saved"], payload["called"]["outcome"])


if __name__ == "__main__":
    import asyncio

    asyncio.run(_amain())
