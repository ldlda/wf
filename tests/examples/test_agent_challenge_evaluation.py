from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

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
