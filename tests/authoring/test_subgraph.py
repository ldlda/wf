from __future__ import annotations

from pydantic import BaseModel

from wf_authoring import build_registry, subgraph_node
from wf_core import RuntimeContext
from wf_core.demo_workflow import build_demo_registry, build_demo_workflow


def test_subgraph_node_wraps_compiled_workflow() -> None:
    class ChildInput(BaseModel):
        folder_id: str
        should_email: bool

    class ChildOutput(BaseModel):
        summary: str
        email_status: str

    child_workflow = build_demo_workflow()
    child_registry = build_demo_registry()
    wrapped = subgraph_node(
        name="wrapped_demo",
        workflow=child_workflow,
        registry=child_registry,
        input_model=ChildInput,
        output_model=ChildOutput,
    )

    registry = build_registry(wrapped)
    result = registry["wrapped_demo"](
        {"folder_id": "demo-folder", "should_email": False},
        RuntimeContext(current_node_id="parent"),
    )

    assert result["outcome"] == "ok"
    assert result["output"]["email_status"] == "skipped"
    assert "summary" in result["output"]
