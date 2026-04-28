from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from pydantic import BaseModel

from wf_core import RuntimeContext, Workflow, execute_workflow

from .spec import NodeSpec

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


def subgraph_node(
    *,
    name: str,
    workflow: Workflow,
    registry: Mapping[str, Any],
    input_model: type[InputT],
    output_model: type[OutputT],
    description: str | None = None,
) -> NodeSpec[InputT, OutputT]:
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
