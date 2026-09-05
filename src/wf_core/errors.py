from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wf_core.run_state import ExecutionFrame, RunState


class WorkflowExecutionError(RuntimeError):
    pass


class WorkflowStepLimitExceeded(WorkflowExecutionError):
    """Raised when a run would exceed its persisted step budget.

    Budget exhaustion is a runtime failure, never a routable workflow outcome:
    no edge may catch it as an ``error`` outcome.
    """

    def __init__(
        self,
        message: str,
        *,
        max_steps: int,
        steps_executed: int,
        frame_id: str,
        scope_id: str,
        node_id: str,
    ) -> None:
        super().__init__(message)
        self.max_steps = max_steps
        self.steps_executed = steps_executed
        self.frame_id = frame_id
        self.scope_id = scope_id
        self.node_id = node_id

    @classmethod
    def from_run(
        cls, run: RunState, frame: ExecutionFrame, node_id: str
    ) -> WorkflowStepLimitExceeded:
        """Build an exhaustion error for the denied dispatch of ``node_id``."""
        return cls(
            f"workflow {run.workflow_name!r} exceeded its step budget "
            f"(max_steps={run.limits.max_steps}, "
            f"steps_executed={run.steps_executed}, "
            f"frame_id={frame.id!r}, scope_id={frame.scope_id!r}, "
            f"next_node_id={node_id!r})",
            max_steps=run.limits.max_steps,
            steps_executed=run.steps_executed,
            frame_id=frame.id,
            scope_id=frame.scope_id,
            node_id=node_id,
        )


__all__ = ["WorkflowExecutionError", "WorkflowStepLimitExceeded"]
