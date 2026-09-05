"""Run-wide step budget policy and admission.

One finite, persisted counter (``RunState.steps_executed``) covers every frame
and subgraph scope in a run. Admission happens immediately before step dispatch:
an admitted attempt increments the counter and stamps the selected frame with
its one-based step number; a denied attempt raises without incrementing and
without invoking any handler. This slice deliberately adds no per-step durable
checkpoints; the counter is persisted inside the existing stopped-run envelope.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from wf_core.errors import WorkflowStepLimitExceeded

if TYPE_CHECKING:
    from wf_core.run_state import ExecutionFrame, RunState


def admit_step_attempt(run: RunState, frame: ExecutionFrame, node_id: str) -> int:
    """Admit one step attempt for ``frame`` about to dispatch ``node_id``.

    On success the run-wide counter is incremented, the frame remembers the
    assigned step number, and that number is returned. When the budget is
    already exhausted the counter is left untouched, the frame keeps its
    previous number, and ``WorkflowStepLimitExceeded`` is raised before any
    handler runs.
    """
    if run.steps_executed >= run.limits.max_steps:
        raise WorkflowStepLimitExceeded.from_run(run, frame, node_id)
    run.steps_executed += 1
    frame.step_number = run.steps_executed
    return frame.step_number


def remaining_step_attempts(run: RunState) -> int:
    """Return the unspent budget, floored at zero (never negative)."""
    return run.steps_remaining
