from __future__ import annotations

from pathlib import Path

from examples.agent_challenges.manifests import load_challenge_manifest
from examples.agent_challenges.models import InstructionProfile
from examples.agent_challenges.run_matrix import (
    ModelProfile,
    build_matrix_tasks,
    parse_model_profile,
)

from .test_agent_challenge_harness_v2 import _write_manifest


def test_parse_model_profile_defaults_variant() -> None:
    parsed = parse_model_profile("opencode/mimo-v2.5-free")

    assert parsed == ModelProfile("opencode/mimo-v2.5-free", "high")


def test_parse_model_profile_accepts_explicit_variant() -> None:
    parsed = parse_model_profile("opencode/deepseek-v4-flash-free=max")

    assert parsed == ModelProfile("opencode/deepseek-v4-flash-free", "max")


def test_matrix_tasks_allocate_indices_across_profiles(tmp_path: Path) -> None:
    challenge = load_challenge_manifest(_write_manifest(tmp_path / "challenge"))
    (challenge.root / "results").mkdir()
    existing = (
        challenge.root / "results" / "opencode_deepseek-v4-flash-free-trial-002.json"
    )
    existing.write_text("{}", encoding="utf-8")

    tasks = build_matrix_tasks(
        challenges=[challenge],
        profiles=[InstructionProfile.NONE, InstructionProfile.SKILLS],
        models=[ModelProfile("opencode/deepseek-v4-flash-free", "max")],
        trials=2,
    )

    assert [task.index for task in tasks] == [3, 4, 5, 6]
    assert [task.profile for task in tasks] == [
        InstructionProfile.NONE,
        InstructionProfile.NONE,
        InstructionProfile.SKILLS,
        InstructionProfile.SKILLS,
    ]


def test_run_trials_concurrency_invokes_all_indices(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    from examples.agent_challenges import run_trials

    manifest = _write_manifest(tmp_path / "challenge")
    seen: list[int] = []

    def fake_run_v2_trial(*args: object, **kwargs: object) -> dict[str, object]:
        index = kwargs["index"]
        assert isinstance(index, int)
        seen.append(index)
        return {
            "task_outcome": "success",
            "evaluation_validity": "clean",
            "duration_seconds": 1.0,
            "result_path": f"trial-{index}.json",
            "report_paths": {},
        }

    monkeypatch.setattr(run_trials, "run_v2_trial", fake_run_v2_trial)

    exit_code = run_trials.main(
        [
            "--challenge",
            str(manifest),
            "--instruction-profile",
            "none",
            "--model",
            "opencode/test",
            "--trials",
            "3",
            "--concurrency",
            "2",
            "--instruction-bundle",
            str(
                Path(__file__).resolve().parents[2]
                / "examples/agent_challenges/instruction_bundles/workflow_cli.yaml"
            ),
        ]
    )

    assert exit_code == 0
    assert sorted(seen) == [1, 2, 3]
    assert '"trial_count": 3' in capsys.readouterr().out
