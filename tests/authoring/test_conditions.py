from __future__ import annotations

from wf_authoring import exists, expr, not_, state, state_path
from wf_core.conditions import eval_condition
from wf_core.models.conditions import BinaryCondition, ExistsCondition, PathOperand
from wf_core.paths import GraphSourcePath


def test_condition_dsl_compiles_to_core_condition() -> None:
    condition = expr(state_path("should_email")).eq(True) & exists(
        state_path("summary")
    )

    dumped = condition.to_condition().model_dump(mode="json")

    assert dumped["op"] == "and"
    assert dumped["args"][0]["left"]["path"] == {
        "root": "state",
        "parts": ["should_email"],
    }
    assert dumped["args"][0]["right"]["value"] is True
    assert dumped["args"][1]["path"] == {"root": "state", "parts": ["summary"]}


def test_condition_dsl_compiles_authoring_paths_to_typed_core_paths() -> None:
    comparison = state("score").gt(expr(state_path("threshold"))).to_condition()
    existence = exists(state_path("summary")).to_condition()

    assert isinstance(comparison, BinaryCondition)
    assert isinstance(comparison.left, PathOperand)
    assert isinstance(comparison.right, PathOperand)
    assert comparison.left.path == GraphSourcePath.state("score")
    assert comparison.right.path == GraphSourcePath.state("threshold")
    assert comparison.model_dump(mode="json")["left"]["path"] == {
        "root": "state",
        "parts": ["score"],
    }
    assert isinstance(existence, ExistsCondition)
    assert existence.path == GraphSourcePath.state("summary")
    assert existence.model_dump(mode="json")["path"] == {
        "root": "state",
        "parts": ["summary"],
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
