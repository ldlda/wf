from __future__ import annotations

from wf_authoring import exists, expr, state_path


def test_condition_dsl_compiles_to_core_condition() -> None:
    condition = expr(state_path("should_email")).eq(True) & exists(
        state_path("summary")
    )

    assert condition.to_condition().model_dump() == {
        "op": "and",
        "args": [
            {
                "op": "eq",
                "left": {"path": "state.should_email"},
                "right": {"value": True},
            },
            {
                "op": "exists",
                "path": "state.summary",
            },
        ],
    }
