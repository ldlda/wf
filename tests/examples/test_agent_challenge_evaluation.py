from __future__ import annotations

import json
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
COHORT_PATH = ROOT / "docs" / "thesis" / "agent-challenge-cohort.json"


def test_primary_agent_challenge_cohort_is_complete_and_audited() -> None:
    from examples.agent_challenges.evaluation import load_evaluation_cohort

    cohort = load_evaluation_cohort(COHORT_PATH, repository_root=ROOT)

    assert len(cohort.trials) == 36
    assert {trial.wave for trial in cohort.trials} == {1, 2, 3}
    assert Counter(trial.manual_outcome for trial in cohort.trials) == {
        "pass": 27,
        "invalid": 8,
        "fail": 1,
    }

    cells = Counter(
        (trial.challenge, trial.model, trial.profile) for trial in cohort.trials
    )
    assert len(cells) == 12
    assert set(cells.values()) == {3}


def test_primary_cohort_preserves_automatic_and_manual_outcomes() -> None:
    from examples.agent_challenges.evaluation import load_evaluation_cohort

    cohort = load_evaluation_cohort(COHORT_PATH, repository_root=ROOT)
    outcome_pairs = Counter(
        (trial.task_outcome, trial.manual_outcome) for trial in cohort.trials
    )

    assert outcome_pairs == {
        ("success", "pass"): 24,
        ("success", "invalid"): 7,
        ("failed", "pass"): 3,
        ("failed", "invalid"): 1,
        ("failed", "fail"): 1,
    }


def test_primary_cohort_snapshot_loads_without_local_report_files(
    tmp_path: Path,
) -> None:
    from examples.agent_challenges.evaluation import load_evaluation_cohort

    manifest = json.loads(COHORT_PATH.read_text(encoding="utf-8"))
    assert all(len(run["report_sha256"]) == 64 for run in manifest["runs"])
    snapshot = tmp_path / "agent-challenge-cohort.json"
    snapshot.write_text(json.dumps(manifest), encoding="utf-8")

    cohort = load_evaluation_cohort(snapshot, repository_root=tmp_path)

    assert len(cohort.trials) == 36


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("profile", "debug", "unsupported evaluation profile"),
        ("task_outcome", "unknown", "unsupported task outcome"),
        ("audit_notes", ["not", "text"], "audit_notes must be a string"),
    ],
)
def test_evaluation_cohort_rejects_unknown_or_mistyped_run_values(
    tmp_path: Path, field: str, value: object, message: str
) -> None:
    from examples.agent_challenges.evaluation import load_evaluation_cohort

    manifest = json.loads(COHORT_PATH.read_text(encoding="utf-8"))
    manifest["runs"][0][field] = value
    snapshot = tmp_path / "agent-challenge-cohort.json"
    snapshot.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_evaluation_cohort(snapshot, repository_root=tmp_path)


def test_evaluation_figures_reject_unknown_direct_trial_values() -> None:
    import matplotlib.pyplot as plt

    from examples.agent_challenges.evaluation import load_evaluation_cohort
    from examples.agent_challenges.evaluation_figures import (
        _automatic_vs_manual,
        _scatter_metric,
    )

    cohort = load_evaluation_cohort(COHORT_PATH, repository_root=ROOT)
    figure, axis = plt.subplots()
    try:
        with pytest.raises(ValueError, match="unsupported evaluation model"):
            _scatter_metric(
                axis,
                [replace(cohort.trials[0], model="unknown-model")],
                metric="duration",
            )
        with pytest.raises(ValueError, match="unsupported evaluation profile"):
            _scatter_metric(
                axis,
                [replace(cohort.trials[0], profile="unknown-profile")],
                metric="duration",
            )
        invalid_cohort = replace(
            cohort,
            trials=(replace(cohort.trials[0], task_outcome="unknown"),),
        )
        with pytest.raises(ValueError, match="unsupported task outcomes"):
            _automatic_vs_manual(invalid_cohort, plt)
    finally:
        plt.close(figure)


def test_evaluation_generator_prints_paths_outside_repository(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from docs.thesis import generate_agent_challenge_evaluation as generator

    generated = tmp_path / "agent-challenge-results.md"
    monkeypatch.setattr(
        generator,
        "generate",
        lambda **_kwargs: (generated,),
    )

    assert generator.main(["--output-dir", str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip() == "agent-challenge-results.md"


def test_evaluation_renderer_writes_stable_svg_and_pdf_names(tmp_path: Path) -> None:
    from examples.agent_challenges.evaluation import (
        FIGURE_STEMS,
        load_evaluation_cohort,
        render_evaluation_figures,
    )

    cohort = load_evaluation_cohort(COHORT_PATH, repository_root=ROOT)
    written = render_evaluation_figures(cohort, tmp_path)

    expected = {
        tmp_path / f"{stem}.{suffix}"
        for stem in FIGURE_STEMS
        for suffix in ("svg", "pdf")
    }
    assert set(written) == expected
    assert all(path.stat().st_size > 0 for path in written)


def test_evaluation_figures_are_byte_stable_across_regeneration(
    tmp_path: Path,
) -> None:
    from examples.agent_challenges.evaluation import (
        load_evaluation_cohort,
        render_evaluation_figures,
    )

    cohort = load_evaluation_cohort(COHORT_PATH, repository_root=ROOT)
    first = render_evaluation_figures(cohort, tmp_path)
    first_bytes = {path.name: path.read_bytes() for path in first}

    second = render_evaluation_figures(cohort, tmp_path)

    assert {path.name: path.read_bytes() for path in second} == first_bytes


def test_evaluation_markdown_states_counts_and_longitudinal_limit() -> None:
    from examples.agent_challenges.evaluation import (
        load_evaluation_cohort,
        render_evaluation_markdown,
    )

    cohort = load_evaluation_cohort(COHORT_PATH, repository_root=ROOT)
    markdown = render_evaluation_markdown(cohort)

    assert "36 manually audited trials" in markdown
    assert "27 clean product-path passes under the campaign rules" in markdown
    assert "not a model-success-rate estimate" in markdown
    assert "8 invalid evaluation samples" in markdown
    assert "and 1 failure" in markdown
    assert "not a controlled model comparison" in markdown
    assert "agent-challenge-audited-outcomes-by-cell.svg" in markdown
    assert "agent-challenge-longitudinal-outcomes.svg" in markdown
    assert "Figure [@fig:" not in markdown
