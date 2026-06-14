from __future__ import annotations

import pytest

from examples.browser_click_workflow.ops import (
    CollectSnapshotsInput,
    OpenPageInput,
    WaitForClickInput,
    _active_session_count,
    _collect_snapshots,
    _open_click_page,
    _wait_for_click,
)


def test_browser_click_source_simulates_click_and_cleans_up() -> None:
    opened = _open_click_page(
        OpenPageInput(button_label="Launch Workflow", open_browser=False)
    )

    assert opened.before.clicked is False
    assert opened.before.button_text == "Launch Workflow"
    assert opened.before.status_text == "Waiting for click"

    clicked = _wait_for_click(
        WaitForClickInput(
            session_id=opened.session_id, simulate=True, timeout_seconds=2
        )
    )
    result = _collect_snapshots(
        CollectSnapshotsInput(
            session_id=opened.session_id,
            before=opened.before,
            after=clicked.after,
        )
    )

    assert result.before.clicked is False
    assert result.after.clicked is True
    assert result.after.status_text == "Button clicked"
    assert result.closed is True
    assert _active_session_count() == 0


def test_browser_click_source_human_timeout_cleans_up() -> None:
    opened = _open_click_page(OpenPageInput(open_browser=False))

    with pytest.raises(TimeoutError, match="timed out waiting for click"):
        _wait_for_click(
            WaitForClickInput(
                session_id=opened.session_id,
                simulate=False,
                timeout_seconds=0.01,
            )
        )

    _collect_snapshots(
        CollectSnapshotsInput(
            session_id=opened.session_id,
            before=opened.before,
            after=opened.before,
        )
    )
    assert _active_session_count() == 0
