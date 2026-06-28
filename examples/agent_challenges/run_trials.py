"""Central CLI for running profiled agent challenge trials."""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    from .manifests import load_challenge_manifest
    from .models import InstructionProfile
    from .runner import run_v2_trial
    from .workspace import starting_trial_index
except ImportError:
    _project_root = Path(__file__).resolve().parents[2]
    if str(_project_root) not in sys.path:
        sys.path.insert(0, str(_project_root))
    from examples.agent_challenges.manifests import load_challenge_manifest
    from examples.agent_challenges.models import InstructionProfile
    from examples.agent_challenges.runner import run_v2_trial
    from examples.agent_challenges.workspace import starting_trial_index


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--challenge",
        type=Path,
        required=True,
        help="Path to challenge.yaml",
    )
    parser.add_argument(
        "--instruction-profile",
        "--profile",
        dest="instruction_profile",
        type=str,
        choices=[p.value for p in InstructionProfile],
        required=True,
        help="Instruction profile for this trial",
    )
    parser.add_argument("--model", default="opencode/mimo-v2.5-free")
    parser.add_argument("--variant", default="high")
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Maximum number of trials for this model/profile/challenge to run at once.",
    )
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    parser.add_argument(
        "--attach",
        dest="attach_url",
        default=None,
        help="Attach to a running opencode server URL.",
    )
    parser.add_argument("--results-dir", type=Path, default=None)
    parser.add_argument("--workspaces-dir", type=Path, default=None)
    parser.add_argument(
        "--instruction-bundle",
        type=Path,
        default=Path(__file__).resolve().parents[2]
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

    challenge = load_challenge_manifest(args.challenge)
    profile = InstructionProfile(args.instruction_profile)

    results_dir = args.results_dir or challenge.root / "results"
    workspaces_dir = args.workspaces_dir or challenge.root / "workspaces"

    first_index = starting_trial_index(
        model=args.model,
        results_dir=results_dir,
        workspaces_dir=workspaces_dir,
    )

    def _run_one(index: int) -> dict[str, object]:
        result = run_v2_trial(
            challenge,
            profile=profile,
            model=args.model,
            variant=args.variant,
            index=index,
            workspaces_dir=workspaces_dir,
            results_dir=results_dir,
            instruction_bundle=args.instruction_bundle,
            timeout_seconds=args.timeout_seconds,
            attach_url=args.attach_url,
        )
        return {
            "index": index,
            "task_outcome": result["task_outcome"],
            "evaluation_validity": result["evaluation_validity"],
            "duration_seconds": result["duration_seconds"],
            "result_path": result.get("result_path"),
            "report_paths": result.get("report_paths"),
        }

    summaries: list[dict[str, object]] = []
    indices = list(range(first_index, first_index + args.trials))
    with ThreadPoolExecutor(max_workers=min(args.concurrency, args.trials)) as pool:
        futures = [pool.submit(_run_one, index) for index in indices]
        for future in as_completed(futures):
            summary = future.result()
            summaries.append(summary)
            print(json.dumps(summary, sort_keys=True))

    success_count = sum(1 for s in summaries if s["task_outcome"] == "success")
    print(json.dumps({"success_count": success_count, "trial_count": len(summaries)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
