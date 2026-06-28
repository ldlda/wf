"""Run a challenge/profile/model matrix with bounded global concurrency."""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from .manifests import load_challenge_manifest
    from .models import InstructionProfile, LoadedChallenge
    from .runner import run_v2_trial
    from .workspace import PROJECT_ROOT, starting_trial_index
except ImportError:
    _project_root = Path(__file__).resolve().parents[2]
    if str(_project_root) not in sys.path:
        sys.path.insert(0, str(_project_root))
    from examples.agent_challenges.manifests import load_challenge_manifest
    from examples.agent_challenges.models import InstructionProfile, LoadedChallenge
    from examples.agent_challenges.runner import run_v2_trial
    from examples.agent_challenges.workspace import PROJECT_ROOT, starting_trial_index


DEFAULT_CHALLENGES = (
    PROJECT_ROOT / "examples/agent_challenges/browser_click_challenge/challenge.yaml",
    PROJECT_ROOT / "examples/agent_challenges/report_workflow_challenge/challenge.yaml",
)
DEFAULT_PROFILES = (
    InstructionProfile.NONE,
    InstructionProfile.SKILLS,
    InstructionProfile.ALL,
)


@dataclass(frozen=True, slots=True)
class ModelProfile:
    model: str
    variant: str


DEFAULT_MODELS = (
    ModelProfile("opencode/deepseek-v4-flash-free", "max"),
    ModelProfile("opencode/mimo-v2.5-free", "high"),
    ModelProfile("opencode/nemotron-3-ultra-free", "high"),
)


@dataclass(frozen=True, slots=True)
class MatrixTask:
    challenge: LoadedChallenge
    profile: InstructionProfile
    model: str
    variant: str
    index: int
    workspaces_dir: Path
    results_dir: Path


def parse_model_profile(raw: str) -> ModelProfile:
    """Parse MODEL or MODEL=VARIANT values from CLI flags."""
    model, separator, variant = raw.partition("=")
    if not model:
        raise ValueError("model cannot be empty")
    if separator and not variant:
        raise ValueError("variant cannot be empty when using MODEL=VARIANT")
    return ModelProfile(model=model, variant=variant if separator else "high")


def build_matrix_tasks(
    *,
    challenges: list[LoadedChallenge],
    profiles: list[InstructionProfile],
    models: list[ModelProfile],
    trials: int,
) -> list[MatrixTask]:
    """Allocate unique trial indices for each challenge/model across profiles."""
    tasks: list[MatrixTask] = []
    for challenge in challenges:
        results_dir = challenge.root / "results"
        workspaces_dir = challenge.root / "workspaces"
        next_indices: dict[str, int] = {}
        for model in models:
            next_index = next_indices.setdefault(
                model.model,
                starting_trial_index(
                    model=model.model,
                    results_dir=results_dir,
                    workspaces_dir=workspaces_dir,
                ),
            )
            for profile in profiles:
                for _ in range(trials):
                    tasks.append(
                        MatrixTask(
                            challenge=challenge,
                            profile=profile,
                            model=model.model,
                            variant=model.variant,
                            index=next_index,
                            workspaces_dir=workspaces_dir,
                            results_dir=results_dir,
                        )
                    )
                    next_index += 1
            next_indices[model.model] = next_index
    return tasks


def _summary_from_result(task: MatrixTask, result: dict[str, Any]) -> dict[str, object]:
    return {
        "challenge": task.challenge.manifest.id,
        "instruction_profile": task.profile.value,
        "model": task.model,
        "variant": task.variant,
        "index": task.index,
        "task_outcome": result["task_outcome"],
        "evaluation_validity": result["evaluation_validity"],
        "duration_seconds": result["duration_seconds"],
        "result_path": result.get("result_path"),
        "report_paths": result.get("report_paths"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--challenge",
        action="append",
        type=Path,
        default=None,
        help="Path to challenge.yaml. May be repeated. Defaults to all bundled challenges.",
    )
    parser.add_argument(
        "--instruction-profile",
        "--profile",
        dest="instruction_profile",
        action="append",
        choices=[p.value for p in InstructionProfile],
        default=None,
        help="Instruction profile. May be repeated. Defaults to none, skills, all.",
    )
    parser.add_argument(
        "--model",
        action="append",
        default=None,
        help=(
            "Model profile as MODEL or MODEL=VARIANT. May be repeated. "
            "Defaults to the standard free OpenCode model set."
        ),
    )
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    parser.add_argument("--attach", dest="attach_url", default=None)
    parser.add_argument(
        "--instruction-bundle",
        type=Path,
        default=PROJECT_ROOT
        / "examples"
        / "agent_challenges"
        / "instruction_bundles"
        / "workflow_cli.yaml",
    )
    args = parser.parse_args(argv)

    if args.trials < 1:
        parser.error("--trials must be >= 1")
    if args.concurrency < 1:
        parser.error("--concurrency must be >= 1")

    try:
        challenges = [
            load_challenge_manifest(path)
            for path in (args.challenge or DEFAULT_CHALLENGES)
        ]
        profiles = [
            InstructionProfile(value)
            for value in (
                args.instruction_profile or [p.value for p in DEFAULT_PROFILES]
            )
        ]
        models = [parse_model_profile(raw) for raw in (args.model or [])] or list(
            DEFAULT_MODELS
        )
    except ValueError as exc:
        parser.error(str(exc))

    tasks = build_matrix_tasks(
        challenges=challenges,
        profiles=profiles,
        models=models,
        trials=args.trials,
    )

    def _run_task(task: MatrixTask) -> dict[str, object]:
        result = run_v2_trial(
            task.challenge,
            profile=task.profile,
            model=task.model,
            variant=task.variant,
            index=task.index,
            workspaces_dir=task.workspaces_dir,
            results_dir=task.results_dir,
            instruction_bundle=args.instruction_bundle,
            timeout_seconds=args.timeout_seconds,
            attach_url=args.attach_url,
        )
        return _summary_from_result(task, result)

    summaries: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=min(args.concurrency, len(tasks))) as pool:
        futures = [pool.submit(_run_task, task) for task in tasks]
        for future in as_completed(futures):
            summary = future.result()
            summaries.append(summary)
            print(json.dumps(summary, sort_keys=True))

    success_count = sum(1 for item in summaries if item["task_outcome"] == "success")
    print(json.dumps({"success_count": success_count, "trial_count": len(summaries)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
