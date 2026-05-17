from __future__ import annotations

from wf_authoring import exists, expr, not_, state, state_path
from wf_core.conditions import eval_condition


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


def test_condition_dsl_supports_not_ge_and_ne() -> None:
    condition = not_(
        state("score").ge(10) & state("score").le(20) & state("status").ne("blocked")
    )
    compiled = condition.to_condition()

    assert compiled.model_dump()["op"] == "not"
    assert eval_condition(
        compiled,
        state={"score": 7, "status": "ready"},
        workflow_input={},
        context_data=None,
    )
