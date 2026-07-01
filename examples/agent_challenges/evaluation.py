from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .names import short_challenge_name, short_model_name

FIGURE_STEMS = (
    "agent-challenge-audited-outcomes-by-cell",
    "agent-challenge-automatic-vs-manual-outcomes",
    "agent-challenge-longitudinal-outcomes",
    "agent-challenge-duration",
    "agent-challenge-token-volume",
)
_MANUAL_OUTCOMES = frozenset({"pass", "invalid", "fail"})
_TASK_OUTCOMES = frozenset({"success", "failed", "timeout", "runner_error"})
_EVALUATION_PROFILES = frozenset({"none", "skills", "all"})
_CHALLENGE_ORDER = {"browser": 0, "report": 1}
_MODEL_ORDER = {"deepseek": 0, "mimo": 1}
_PROFILE_ORDER = {"none": 0, "skills": 1, "all": 2}


@dataclass(frozen=True, slots=True)
class EvaluationTrial:
    """One manually audited trial selected into an evaluation cohort."""

    report_path: Path
    wave: int
    challenge: str
    model: str
    profile: str
    trial_index: int
    repository_commit: str
    base_prompt_hash: str
    manual_outcome: str
    task_outcome: str
    duration_seconds: float
    tokens_total: int
    audit_notes: str


@dataclass(frozen=True, slots=True)
class EvaluationCohort:
    """Immutable cohort metadata and its validated report projections."""

    cohort_id: str
    title: str
    selection_rule: str
    limitations: tuple[str, ...]
    trials: tuple[EvaluationTrial, ...]


def _object(value: object, *, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return value


def _string(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _integer(value: object, *, field: str) -> int:
    if not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    return value


def _report_path(repository_root: Path, value: object) -> Path:
    relative = Path(_string(value, field="runs[].report"))
    if relative.is_absolute():
        raise ValueError("runs[].report must be relative to the repository root")
    resolved = (repository_root / relative).resolve()
    if not resolved.is_relative_to(repository_root.resolve()):
        raise ValueError(f"report path escapes repository root: {relative}")
    return resolved


def _report_sha256(value: object, *, report_path: Path) -> str:
    """Validate snapshot provenance and, when available, its local report."""
    expected = _string(value, field="runs[].report_sha256")
    if len(expected) != 64 or any(
        character not in "0123456789abcdef" for character in expected
    ):
        raise ValueError(f"invalid report SHA-256 for {report_path}")
    if report_path.is_file():
        actual = hashlib.sha256(report_path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(
                f"local report does not match cohort snapshot: {report_path}"
            )
    return expected


def _load_trial(
    run: dict[str, Any], report_path: Path, *, wave: int
) -> EvaluationTrial:
    _report_sha256(run.get("report_sha256"), report_path=report_path)
    manual_outcome = _string(run.get("manual_outcome"), field="runs[].manual_outcome")
    if manual_outcome not in _MANUAL_OUTCOMES:
        raise ValueError(
            f"unsupported manual outcome {manual_outcome!r}: {report_path}"
        )
    profile = _string(run.get("profile"), field="runs[].profile")
    if profile not in _EVALUATION_PROFILES:
        raise ValueError(f"unsupported evaluation profile {profile!r}: {report_path}")
    task_outcome = _string(run.get("task_outcome"), field="runs[].task_outcome")
    if task_outcome not in _TASK_OUTCOMES:
        raise ValueError(f"unsupported task outcome {task_outcome!r}: {report_path}")
    raw_audit_notes = run.get("audit_notes")
    if raw_audit_notes is None:
        audit_notes = ""
    elif isinstance(raw_audit_notes, str):
        audit_notes = raw_audit_notes
    else:
        raise ValueError(f"runs[].audit_notes must be a string: {report_path}")

    duration = run.get("duration_seconds")
    if not isinstance(duration, int | float):
        raise ValueError(f"runs[].duration_seconds must be numeric: {report_path}")

    return EvaluationTrial(
        report_path=report_path,
        wave=wave,
        challenge=short_challenge_name(
            _string(run.get("challenge"), field="runs[].challenge")
        ),
        model=short_model_name(_string(run.get("model"), field="runs[].model")),
        profile=profile,
        trial_index=_integer(run.get("trial_index"), field="runs[].trial_index"),
        repository_commit=_string(
            run.get("repository_commit"), field="runs[].repository_commit"
        ),
        base_prompt_hash=_string(
            run.get("base_prompt_hash"), field="runs[].base_prompt_hash"
        ),
        manual_outcome=manual_outcome,
        task_outcome=task_outcome,
        duration_seconds=float(duration),
        tokens_total=_integer(run.get("tokens_total"), field="runs[].tokens_total"),
        audit_notes=audit_notes,
    )


def load_evaluation_cohort(
    manifest_path: Path, *, repository_root: Path
) -> EvaluationCohort:
    """Load an explicit cohort manifest and validate every report projection."""
    manifest = _object(
        json.loads(manifest_path.read_text(encoding="utf-8")), field=str(manifest_path)
    )
    if manifest.get("schema_version") != 1:
        raise ValueError("agent challenge cohort schema_version must be 1")
    raw_runs = manifest.get("runs")
    if not isinstance(raw_runs, list) or not raw_runs:
        raise ValueError("agent challenge cohort runs must be a non-empty list")

    trials: list[EvaluationTrial] = []
    seen: set[Path] = set()
    for index, raw_run in enumerate(raw_runs):
        run = _object(raw_run, field=f"runs[{index}]")
        wave = _integer(run.get("wave"), field=f"runs[{index}].wave")
        if wave < 1:
            raise ValueError(f"runs[{index}].wave must be positive")
        report_path = _report_path(repository_root, run.get("report"))
        if report_path in seen:
            raise ValueError(f"duplicate report in cohort: {report_path}")
        seen.add(report_path)
        trials.append(_load_trial(run, report_path, wave=wave))

    limitations = manifest.get("limitations")
    if not isinstance(limitations, list) or not all(
        isinstance(item, str) and item for item in limitations
    ):
        raise ValueError("limitations must be a list of non-empty strings")

    return EvaluationCohort(
        cohort_id=_string(manifest.get("cohort_id"), field="cohort_id"),
        title=_string(manifest.get("title"), field="title"),
        selection_rule=_string(manifest.get("selection_rule"), field="selection_rule"),
        limitations=tuple(limitations),
        trials=tuple(trials),
    )


def render_evaluation_figures(
    cohort: EvaluationCohort, output_dir: Path
) -> tuple[Path, ...]:
    """Render the cohort through the optional Matplotlib figure layer."""
    # Keeping plotting imports out of this data module lets summary tooling run
    # in minimal environments that do not install thesis build dependencies.
    from .evaluation_figures import render_evaluation_figures as render

    return render(cohort, output_dir)


def _cell_rows(cohort: EvaluationCohort) -> list[tuple[str, Counter[str]]]:
    grouped: dict[tuple[str, str, str], Counter[str]] = {}
    for trial in cohort.trials:
        key = (trial.challenge, trial.model, trial.profile)
        grouped.setdefault(key, Counter())[trial.manual_outcome] += 1
    keys = sorted(
        grouped,
        key=lambda key: (
            _CHALLENGE_ORDER.get(key[0], 99),
            _MODEL_ORDER.get(key[1], 99),
            _PROFILE_ORDER.get(key[2], 99),
        ),
    )
    return [
        (f"{challenge} / {model} / {profile}", grouped[(challenge, model, profile)])
        for challenge, model, profile in keys
    ]


def render_evaluation_markdown(cohort: EvaluationCohort) -> str:
    """Render the checked cohort as a compact, auditable Markdown appendix."""
    outcomes = Counter(trial.manual_outcome for trial in cohort.trials)
    lines = [
        "## Audited Agent Challenge Campaign",
        "",
        (
            f"The primary campaign contains {len(cohort.trials)} manually audited "
            f"trials: {outcomes['pass']} clean product-path passes under the "
            f"campaign rules, {outcomes['invalid']} invalid evaluation samples, "
            f"and {outcomes['fail']} failure. These counts are not a "
            f"model-success-rate estimate."
        ),
        "",
        (
            "The campaign crosses two challenges × two hosted models × three "
            "instruction profiles (`none`, `skills`, and `all`) = 12 cells, with "
            "three repetitions per cell (n=3). The checked cohort snapshot records "
            "report hashes, prompt hashes, the repository commit, automatic metrics, "
            "and manual-audit outcomes; local raw report files are verified against "
            "those hashes when present."
        ),
        "",
        (
            "Because repository snapshots and one prompt rule changed between waves, "
            "this is longitudinal engineering evidence, not a controlled model comparison."
        ),
        "",
        "> **Campaign validity note.** This campaign is a bounded longitudinal audit, "
        "not a controlled comparison. Each cell has n=3; waves changed product and "
        "prompt snapshots; all audits were performed by the author.",
        "",
        f"Selection rule: {cohort.selection_rule}",
        "",
        "| Challenge / model / profile | Pass | Invalid | Fail |",
        "| --- | ---: | ---: | ---: |",
    ]
    for label, counts in _cell_rows(cohort):
        lines.append(
            f"| {label} | {counts['pass']} | {counts['invalid']} | {counts['fail']} |"
        )
    lines.extend(
        [
            "",
            ": Audited outcomes by challenge, model, and instruction profile. {#tbl:agent-challenge-outcomes}",
            "",
            (
                "A manual `pass` requires both successful product-path evidence and an "
                "acceptable audit trail. It does not imply the agent avoided every "
                "exploratory read, only that no disqualifying read or bypass was found. "
                "`Invalid` means the sample cannot support the clean benchmark claim, "
                "commonly because the agent read repository or example material outside "
                "its supplied workspace. `Fail` means the challenge contract itself was "
                "not established."
            ),
            "",
            "![Audited outcomes by evaluation cell.](figures/agent-challenge-audited-outcomes-by-cell.svg){#fig:agent-challenge-audited-outcomes-by-cell width=95%}",
            "",
            (
                "[@fig:agent-challenge-audited-outcomes-by-cell] reports all three "
                "repetitions rather than hiding invalid samples. The profile labels are "
                "descriptive; this campaign does not isolate instruction-profile effects. "
                "Profile × wave is confounded because the base prompt changed before "
                "wave 3, so apparent differences may reflect prompt changes, model "
                "updates, or repository drift rather than instruction-layer effects."
            ),
            "",
            "![Automatic task outcomes compared with manual outcomes.](figures/agent-challenge-automatic-vs-manual-outcomes.svg){#fig:agent-challenge-automatic-vs-manual-outcomes width=75%}",
            "",
            (
                "[@fig:agent-challenge-automatic-vs-manual-outcomes] shows why the "
                "manual layer matters. Seven automatically successful trials were invalid "
                "as clean evidence, while three automatically failed reports were accepted "
                "after their saved run evidence and report artifacts were manually audited."
            ),
            "",
            "![Audited outcomes across the three longitudinal waves.](figures/agent-challenge-longitudinal-outcomes.svg){#fig:agent-challenge-longitudinal-outcomes width=75%}",
            "",
            (
                "The waves in [@fig:agent-challenge-longitudinal-outcomes] are not "
                "an improvement curve: product commits, prompt wording, and enforcement "
                "changed. They preserve the chronology needed to study those changes."
            ),
            "",
            "![Wall-clock duration grouped by challenge, instruction profile, model, and wave.](figures/agent-challenge-duration.svg){#fig:agent-challenge-duration width=78%}",
            "",
            (
                "[@fig:agent-challenge-duration] separates the two challenges. Circle "
                "and square markers redundantly identify the models without relying on "
                "color. Wall-clock duration includes hosted-service latency and is not a "
                "normalized model-efficiency metric."
            ),
            "",
            "![Recorded token totals grouped by challenge, instruction profile, model, and wave.](figures/agent-challenge-token-volume.svg){#fig:agent-challenge-token-volume width=78%}",
            "",
            (
                "[@fig:agent-challenge-token-volume] reports OpenCode token totals, which "
                "include cache-read accounting. The figure records observed workload volume; "
                "it is not an efficiency comparison."
            ),
            "",
            "### Campaign Limitations",
            "",
        ]
    )
    lines.extend(f"- {limitation}" for limitation in cohort.limitations)
    return "\n".join(lines) + "\n"
