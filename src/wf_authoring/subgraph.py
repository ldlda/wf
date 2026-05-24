from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from pydantic import BaseModel

from wf_core import (
    RuntimeContext,
    SubgraphNode,
    Workflow,
    execute_workflow,
    execute_workflow_async,
)
from wf_core.models.steps import InputBinding, OutputBinding

from .nodes import NodeSpec

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


def subgraph_ref(
    *,
    id: str,
    workflow: Workflow,
    input: list[InputBinding] | None = None,
    output: list[OutputBinding] | None = None,
    workflow_ref: str | None = None,
    desc: str | None = None,
) -> SubgraphNode:
    """Create a native subgraph boundary from a compiled child workflow contract.

    This does not make the child executable yet. It copies the child workflow's
    public contract into `SubgraphNode` so parent graphs can validate mappings
    and route child workflow outcomes before native child-scope runtime support
    lands.
    """
    return SubgraphNode(
        id=id,
        type="subgraph",
        workflow=workflow_ref or workflow.name,
        desc=desc,
        input_schema=workflow.input_schema,
        output_schema=workflow.output_schema,
        input=input or [],
        output=output or [],
        outcomes=list(workflow.outcomes),
    )


def subgraph_node(
    *,
    name: str,
    workflow: Workflow,
    registry: Mapping[str, Any],
    input_model: type[InputT],
    output_model: type[OutputT],
    description: str | None = None,
) -> NodeSpec[InputT, OutputT]:
    """Wrap a compiled workflow as a sync authoring node.

    This is deliberately only a wrapper-node compatibility helper: the parent
    trace sees one node call, and child interrupts/frames are not promoted into
    native parent subgraph state. Use `async_subgraph_node` when the wrapped
    workflow registry contains async handlers.
    """

    def run_subgraph(payload: InputT, ctx: RuntimeContext) -> OutputT:
        child_run = execute_workflow(
            workflow,
            payload.model_dump(),
            registry,
        )
        return output_model.model_validate(child_run.output)

    return NodeSpec(
        name=name,
        input_model=input_model,
        output_model=output_model,
        outcomes=("ok",),
        fn=run_subgraph,
        description=description or f"Subgraph wrapper for {workflow.name}",
        is_async=False,
    )


def async_subgraph_node(
    *,
    name: str,
    workflow: Workflow,
    registry: Mapping[str, Any],
    input_model: type[InputT],
    output_model: type[OutputT],
    description: str | None = None,
) -> NodeSpec[InputT, OutputT]:
    """Wrap a compiled workflow with async handlers as an async authoring node.

    This keeps async explicit instead of calling `asyncio.run()` from the sync
    wrapper, which would break inside already-running event loops. It is still
    wrapper-node composition, not native subgraph execution.
    """

    async def run_subgraph(payload: InputT, ctx: RuntimeContext) -> OutputT:
        child_run = await execute_workflow_async(
            workflow,
            payload.model_dump(),
            registry,
        )
        return output_model.model_validate(child_run.output)

    return NodeSpec(
        name=name,
        input_model=input_model,
        output_model=output_model,
        outcomes=("ok",),
        fn=run_subgraph,
        description=description or f"Async subgraph wrapper for {workflow.name}",
        is_async=True,
    )
