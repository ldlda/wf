from __future__ import annotations

import pytest

from wf_core.errors import WorkflowExecutionError
from wf_core.models.schemas import SchemaRef, StateSchema
from wf_core.models.workflow import Workflow
from wf_core.run_state import ExecutionFrame, FrameStatus, RunState, RunStatus
from wf_core.runtime.ops.flow import advance_frame
from wf_core.runtime.ops.runs import create_run_state
from wf_core.runtime.scheduler import (
    add_frame,
    block_frame_on_children,
    enqueue_frame,
    select_next_frame,
    wake_frame,
    wake_parent_if_children_complete,
)


def _run() -> RunState:
    return RunState(
        workflow_name="demo",
        status=RunStatus.RUNNING,
        workflow_input={},
        state={},
    )


def test_run_state_serializes_ready_frame_ids() -> None:
    run = RunState(
        workflow_name="demo",
        status=RunStatus.PENDING,
        workflow_input={},
        state={},
        ready_frame_ids=["root"],
    )

    dumped = run.to_dict()

    assert dumped["ready_frame_ids"] == ["root"]


def test_frame_status_has_blocked() -> None:
    assert FrameStatus.BLOCKED == "blocked"


def test_add_frame_rejects_duplicate_frame_ids() -> None:
    run = _run()
    add_frame(run, ExecutionFrame(id="root", kind="root", node_id="a"))

    with pytest.raises(WorkflowExecutionError, match="duplicate frame id"):
        add_frame(run, ExecutionFrame(id="root", kind="root", node_id="a"))


def test_enqueue_is_unique_and_priority_moves_to_front() -> None:
    run = _run()
    add_frame(run, ExecutionFrame(id="a", kind="root", node_id="a"))
    add_frame(run, ExecutionFrame(id="b", kind="root", node_id="b"))

    enqueue_frame(run, "a")
    enqueue_frame(run, "b")
    enqueue_frame(run, "a")
    enqueue_frame(run, "a", front=True)

    assert run.ready_frame_ids == ["a", "b"]


def test_select_next_frame_pops_and_marks_running() -> None:
    run = _run()
    add_frame(run, ExecutionFrame(id="root", kind="root", node_id="a"))
    enqueue_frame(run, "root")

    frame = select_next_frame(run)

    assert frame is not None
    assert frame.id == "root"
    assert frame.status == FrameStatus.RUNNING
    assert run.ready_frame_ids == []
    assert run.current_frame_id == "root"
    assert run.current_node_id == "a"


def test_blocked_frame_is_not_selectable_until_woken() -> None:
    run = _run()
    add_frame(run, ExecutionFrame(id="parent", kind="root", node_id="foreach"))
    block_frame_on_children(run, "parent", ("child",))

    assert select_next_frame(run) is None

    wake_frame(run, "parent")
    selected = select_next_frame(run)

    assert selected is not None
    assert selected.id == "parent"


def test_create_run_state_queues_root_frame() -> None:
    workflow = Workflow(
        name="demo",
        input_schema=SchemaRef(properties={}),
        state_schema=StateSchema(properties={}),
        output_schema=SchemaRef(properties={}),
        node_defs=[],
        start="first",
        nodes=[],
        edges=[],
    )

    run = create_run_state(workflow, {})

    assert run.current_frame_id == "root"
    assert run.current_node_id == "first"
    assert run.ready_frame_ids == ["root"]
    assert run.frames["root"].status == FrameStatus.PENDING


def test_advance_frame_requeues_non_terminal_frame() -> None:
    run = _run()
    add_frame(run, ExecutionFrame(id="root", kind="root", node_id="a"))
    run.current_frame_id = "root"
    run.sync_from_current_frame()
    frame = run.current_frame()
    frame.status = FrameStatus.RUNNING

    advance_frame(run, frame, outcome="ok", next_node_id="b")

    assert frame.status == FrameStatus.PENDING
    assert run.ready_frame_ids == ["root"]
    assert run.current_node_id == "b"


def test_child_completion_wakes_blocked_parent() -> None:
    run = _run()
    add_frame(run, ExecutionFrame(id="parent", kind="root", node_id="foreach"))
    add_frame(
        run,
        ExecutionFrame(
            id="child",
            kind="foreach_iteration",
            node_id="__end__",
            parent_frame_id="parent",
        ),
    )
    block_frame_on_children(run, "parent", ("child",))
    run.frames["child"].status = FrameStatus.COMPLETED

    wake_parent_if_children_complete(run, "child")

    assert run.frames["parent"].status == FrameStatus.PENDING
    assert run.ready_frame_ids == ["parent"]


def test_resume_wakes_interrupted_frame_at_front() -> None:
    run = _run()
    add_frame(run, ExecutionFrame(id="waiting", kind="root", node_id="ask"))
    add_frame(run, ExecutionFrame(id="sibling", kind="root", node_id="work"))
    run.frames["waiting"].status = FrameStatus.INTERRUPTED
    run.frames["sibling"].status = FrameStatus.PENDING
    run.ready_frame_ids = ["sibling"]

    wake_frame(run, "waiting", front=True)

    assert run.ready_frame_ids == ["waiting", "sibling"]
