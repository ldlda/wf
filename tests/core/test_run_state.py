from __future__ import annotations

import pytest

from wf_core.run_state import RunState, RunStatus


def test_current_frame_rejects_missing_frame_id_with_clear_error() -> None:
    run = RunState(
        workflow_name="demo",
        status=RunStatus.RUNNING,
        workflow_input={},
        state={},
        current_frame_id="missing",
    )

    with pytest.raises(ValueError, match="current_frame_id='missing'"):
        run.current_frame()
