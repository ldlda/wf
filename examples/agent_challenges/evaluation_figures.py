from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure

    from .evaluation import EvaluationCohort, EvaluationTrial

_OUTCOMES = ("pass", "invalid", "fail")
_OUTCOME_COLORS = {
    "pass": "#00796B",
    "invalid": "#E07A1F",
    "fail": "#9E2A2B",
}
_OUTCOME_HATCHES = {"pass": "", "invalid": "///", "fail": "xx"}
_MODEL_STYLES = {
    "deepseek": {"color": "#0067A5", "marker": "o", "offset": -0.13},
    "mimo": {"color": "#D55E00", "marker": "s", "offset": 0.13},
}
_PROFILE_ORDER = {"none": 0, "skills": 1, "all": 2}
_CHALLENGE_ORDER = {"browser": 0, "report": 1}
_MODEL_ORDER = {"deepseek": 0, "mimo": 1}
_TASK_OUTCOME_ORDER = ("success", "failed", "timeout", "runner_error")


def _configure_matplotlib() -> Any:
    """Import Matplotlib with a headless backend suitable for docs builds."""
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "svg.hashsalt": "lda-chat-agent-challenge-evaluation",
            "axes.titleweight": "bold",
            "axes.titlesize": 12,
            "axes.labelcolor": "#28323c",
            "axes.edgecolor": "#8b949e",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.facecolor": "white",
            "axes.facecolor": "#F3F6F7",
            "grid.color": "#C9D1D5",
            "grid.linewidth": 0.6,
        }
    )
    return plt


def _trial_sort_key(trial: EvaluationTrial) -> tuple[int, int, int, int]:
    return (
        _CHALLENGE_ORDER.get(trial.challenge, 99),
        _MODEL_ORDER.get(trial.model, 99),
        _PROFILE_ORDER.get(trial.profile, 99),
        trial.wave,
    )


def _cell_key(trial: EvaluationTrial) -> tuple[str, str, str]:
    return trial.challenge, trial.model, trial.profile


def _ordered_cells(cohort: EvaluationCohort) -> list[tuple[str, str, str]]:
    return sorted(
        {_cell_key(trial) for trial in cohort.trials},
        key=lambda cell: (
            _CHALLENGE_ORDER.get(cell[0], 99),
            _MODEL_ORDER.get(cell[1], 99),
            _PROFILE_ORDER.get(cell[2], 99),
        ),
    )


def _save_figure(
    figure: Figure, output_dir: Path, stem: str, plt: Any
) -> tuple[Path, Path]:
    """Save one source figure in web-native SVG and print-native PDF."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for suffix in ("svg", "pdf"):
        path = output_dir / f"{stem}.{suffix}"
        # Matplotlib otherwise embeds current timestamps, and SVG element IDs
        # use a random salt. Stable metadata makes checked-in figures reproducible.
        metadata = (
            {"Creator": "lda.chat thesis evaluation", "Date": None}
            if suffix == "svg"
            else {
                "Creator": "lda.chat thesis evaluation",
                "CreationDate": None,
                "ModDate": None,
            }
        )
        figure.savefig(
            path,
            bbox_inches="tight",
            pad_inches=0.12,
            metadata=metadata,
        )
        if suffix == "svg":
            # Matplotlib writes SVG path data across lines with trailing spaces.
            # Normalize it so generated figures can pass git whitespace checks.
            lines = path.read_text(encoding="utf-8").splitlines()
            path.write_text(
                "\n".join(line.rstrip() for line in lines) + "\n",
                encoding="utf-8",
                newline="\n",
            )
        written.append(path)
    plt.close(figure)
    return written[0], written[1]


def _outcomes_by_cell(cohort: EvaluationCohort, plt: Any) -> Figure:
    cells = _ordered_cells(cohort)
    counts = {
        cell: Counter(
            trial.manual_outcome for trial in cohort.trials if _cell_key(trial) == cell
        )
        for cell in cells
    }
    labels = [
        f"{challenge}  |  {model}  |  {profile}" for challenge, model, profile in cells
    ]
    figure, axis = plt.subplots(figsize=(9.2, 6.4))
    left = [0] * len(cells)
    for outcome in _OUTCOMES:
        values = [counts[cell][outcome] for cell in cells]
        bars = axis.barh(
            range(len(cells)),
            values,
            left=left,
            label=outcome.capitalize(),
            color=_OUTCOME_COLORS[outcome],
            edgecolor="#263238",
            linewidth=0.55,
            hatch=_OUTCOME_HATCHES[outcome],
            height=0.68,
        )
        for bar, value in zip(bars, values, strict=True):
            if value:
                axis.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_y() + bar.get_height() / 2,
                    str(value),
                    ha="center",
                    va="center",
                    color="#17212B" if outcome == "invalid" else "white",
                    fontweight="bold",
                )
        left = [current + value for current, value in zip(left, values, strict=True)]

    axis.set_yticks(range(len(cells)), labels)
    axis.invert_yaxis()
    axis.set_xticks((0, 1, 2, 3))
    axis.set_xlim(0, 3)
    axis.set_xlabel("Manually audited trials (n=3 per cell)")
    axis.set_title("Audited outcomes by challenge, model, and instruction profile")
    axis.grid(axis="x")
    axis.legend(loc="lower right", frameon=False, ncol=3)
    figure.tight_layout()
    return figure


def _automatic_vs_manual(cohort: EvaluationCohort, plt: Any) -> Figure:
    from matplotlib.colors import LinearSegmentedColormap

    task_labels = tuple(
        outcome
        for outcome in _TASK_OUTCOME_ORDER
        if any(trial.task_outcome == outcome for trial in cohort.trials)
    )
    manual_labels = ("pass", "invalid", "fail")
    unknown_task_outcomes = sorted(
        {trial.task_outcome for trial in cohort.trials} - set(_TASK_OUTCOME_ORDER)
    )
    if unknown_task_outcomes:
        raise ValueError(f"unsupported task outcomes: {unknown_task_outcomes}")
    matrix = [
        [
            sum(
                trial.task_outcome == task and trial.manual_outcome == manual
                for trial in cohort.trials
            )
            for manual in manual_labels
        ]
        for task in task_labels
    ]

    figure, axis = plt.subplots(figsize=(6.8, 3.8))
    count_cmap = LinearSegmentedColormap.from_list(
        "lda_count", ("#F3F6F7", "#79B8B3", "#005F73")
    )
    maximum = max(map(max, matrix))
    image = axis.imshow(matrix, cmap=count_cmap, vmin=0, vmax=maximum)
    for row, values in enumerate(matrix):
        for column, value in enumerate(values):
            axis.text(
                column,
                row,
                str(value),
                ha="center",
                va="center",
                color="white" if value > maximum / 2 else "#17212B",
                fontsize=13,
                fontweight="bold",
            )
    axis.set_xticks(
        range(len(manual_labels)), [label.capitalize() for label in manual_labels]
    )
    axis.set_yticks(
        range(len(task_labels)), [label.capitalize() for label in task_labels]
    )
    axis.set_xlabel("Manual official outcome")
    axis.set_ylabel("Automatic task outcome")
    axis.set_title("Automatic completion does not imply clean evaluation evidence")
    axis.set_xticks([value - 0.5 for value in range(1, len(manual_labels))], minor=True)
    axis.set_yticks([value - 0.5 for value in range(1, len(task_labels))], minor=True)
    axis.grid(which="minor", color="white", linewidth=2)
    axis.tick_params(which="minor", bottom=False, left=False)
    figure.colorbar(image, ax=axis, label="Trial count", shrink=0.82)
    figure.tight_layout()
    return figure


def _longitudinal_outcomes(cohort: EvaluationCohort, plt: Any) -> Figure:
    waves = sorted({trial.wave for trial in cohort.trials})
    counts = {
        wave: Counter(
            trial.manual_outcome for trial in cohort.trials if trial.wave == wave
        )
        for wave in waves
    }
    figure, axis = plt.subplots(figsize=(6.8, 4.0))
    bottom = [0] * len(waves)
    for outcome in _OUTCOMES:
        values = [counts[wave][outcome] for wave in waves]
        bars = axis.bar(
            waves,
            values,
            bottom=bottom,
            label=outcome.capitalize(),
            color=_OUTCOME_COLORS[outcome],
            edgecolor="#263238",
            linewidth=0.55,
            hatch=_OUTCOME_HATCHES[outcome],
            width=0.62,
        )
        for bar, value in zip(bars, values, strict=True):
            if value:
                axis.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_y() + bar.get_height() / 2,
                    str(value),
                    ha="center",
                    va="center",
                    color="#17212B" if outcome == "invalid" else "white",
                    fontweight="bold",
                )
        bottom = [
            current + value for current, value in zip(bottom, values, strict=True)
        ]
    axis.set_xticks(waves, [f"Wave {wave}" for wave in waves])
    axis.set_ylim(0, max(bottom) + 1)
    axis.set_ylabel("Manually audited trials")
    axis.set_title("Outcomes across three evolving product and prompt snapshots")
    axis.grid(axis="y")
    axis.legend(frameon=False, ncol=3, loc="upper center")
    figure.tight_layout()
    return figure


def _scatter_metric(
    axis: Axes,
    trials: list[EvaluationTrial],
    *,
    metric: str,
) -> None:
    profiles = ("none", "skills", "all")
    wave_offsets = {1: -0.055, 2: 0.0, 3: 0.055}
    for trial in sorted(trials, key=_trial_sort_key):
        style = _MODEL_STYLES.get(trial.model)
        if style is None:
            raise ValueError(f"unsupported evaluation model {trial.model!r}")
        if trial.profile not in profiles:
            raise ValueError(f"unsupported evaluation profile {trial.profile!r}")
        x = (
            profiles.index(trial.profile)
            + float(style["offset"])
            + wave_offsets.get(trial.wave, 0.0)
        )
        if metric == "duration":
            value = trial.duration_seconds / 60
        else:
            value = trial.tokens_total / 1_000_000
        axis.scatter(
            x,
            value,
            color=str(style["color"]),
            marker=str(style["marker"]),
            edgecolor="#17212B",
            linewidth=0.65,
            s=86,
            zorder=3,
        )
        axis.annotate(
            str(trial.wave),
            (x, value),
            ha="center",
            va="center",
            color="white",
            fontsize=6,
            fontweight="bold",
            zorder=4,
        )
    axis.set_xticks(
        range(len(profiles)), [profile.capitalize() for profile in profiles]
    )
    axis.set_xlim(-0.42, 2.42)
    axis.grid(axis="y")


def _metric_by_challenge(
    cohort: EvaluationCohort,
    plt: Any,
    *,
    metric: str,
) -> Figure:
    """Render one readable metric panel per challenge."""
    from matplotlib.lines import Line2D

    figure, axes = plt.subplots(2, 1, figsize=(7.4, 6.8), sharex=True)
    challenges = (("browser", "Browser click"), ("report", "Report workflow"))
    for axis, (challenge, challenge_label) in zip(axes, challenges, strict=True):
        trials = [trial for trial in cohort.trials if trial.challenge == challenge]
        _scatter_metric(axis, trials, metric=metric)
        unit = "Minutes" if metric == "duration" else "Million tokens"
        axis.set_ylabel(f"{challenge_label}\n{unit}")

    axes[-1].set_xlabel("Instruction profile")
    legend_handles = [
        Line2D(
            [],
            [],
            color=str(style["color"]),
            marker=str(style["marker"]),
            linestyle="None",
            markeredgecolor="#17212B",
            markersize=8,
            label=f"{model.capitalize()} ({'circle' if model == 'deepseek' else 'square'})",
        )
        for model, style in _MODEL_STYLES.items()
    ]
    title = (
        "Wall-clock duration by profile, model, and wave"
        if metric == "duration"
        else "Recorded token volume by profile, model, and wave"
    )
    figure.suptitle(
        title,
        fontsize=13,
        fontweight="bold",
    )
    figure.legend(
        handles=legend_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.94),
        frameon=False,
        ncol=2,
    )
    figure.text(
        0.5,
        0.015,
        (
            "Point labels 1–3 identify waves."
            if metric == "duration"
            else "Point labels 1–3 identify waves; totals include OpenCode cache-read accounting."
        ),
        ha="center",
        color="#4C5961",
        fontsize=8,
    )
    figure.tight_layout(rect=(0.0, 0.05, 1.0, 0.88))
    return figure


def render_evaluation_figures(
    cohort: EvaluationCohort, output_dir: Path
) -> tuple[Path, ...]:
    """Write all named evaluation figures as SVG and PDF pairs."""
    plt = _configure_matplotlib()
    figures = (
        ("agent-challenge-audited-outcomes-by-cell", _outcomes_by_cell(cohort, plt)),
        (
            "agent-challenge-automatic-vs-manual-outcomes",
            _automatic_vs_manual(cohort, plt),
        ),
        ("agent-challenge-longitudinal-outcomes", _longitudinal_outcomes(cohort, plt)),
        (
            "agent-challenge-duration",
            _metric_by_challenge(cohort, plt, metric="duration"),
        ),
        (
            "agent-challenge-token-volume",
            _metric_by_challenge(cohort, plt, metric="tokens"),
        ),
    )
    written: list[Path] = []
    for stem, figure in figures:
        written.extend(_save_figure(figure, output_dir, stem, plt))
    return tuple(written)
