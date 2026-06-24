from __future__ import annotations

from pathlib import Path

from examples.agent_challenges.manifests import load_challenge_manifest
from examples.agent_challenges.models import InstructionProfile
from examples.agent_challenges.workspace import prepare_v2_trial_workspace

ROOT = Path(__file__).resolve().parents[2]
REPORT_CHALLENGE = (
    ROOT
    / "examples"
    / "agent_challenges"
    / "report_workflow_challenge"
    / "challenge.yaml"
)


def test_report_workflow_manifest_uses_report_source() -> None:
    loaded = load_challenge_manifest(REPORT_CHALLENGE)

    assert loaded.manifest.id == "report_workflow"
    assert loaded.manifest.source.id == "local.report"
    assert loaded.manifest.report.success_assertions == {
        "title_matches": True,
        "markdown_rendered": True,
        "run_failed": False,
    }
    assert loaded.prompt_path.is_file()
    assert loaded.workspace_template.is_dir()


def test_report_challenge_prompt_requires_full_product_lifecycle() -> None:
    loaded = load_challenge_manifest(REPORT_CHALLENGE)
    prompt = loaded.prompt_path.read_text(encoding="utf-8")

    assert "read_notes" in prompt
    assert "extract_report" in prompt
    assert "render_markdown_report" in prompt
    assert "deployment" in prompt.lower()
    assert "run_id" in prompt


def test_report_challenge_workspace_template_contains_safe_input_files(
    tmp_path: Path,
) -> None:
    loaded = load_challenge_manifest(REPORT_CHALLENGE)
    bundle = ROOT / "examples/agent_challenges/instruction_bundles/workflow_cli.yaml"

    workspace = prepare_v2_trial_workspace(
        loaded,
        profile=InstructionProfile.NONE,
        model="model",
        index=1,
        workspaces_dir=tmp_path / "workspaces",
        instruction_bundle=bundle,
    )

    assert (
        (workspace.root / "input.md")
        .read_text(encoding="utf-8")
        .startswith("# Weekly Project Update")
    )
    assert '"text"' in (workspace.root / "run-input.json").read_text(encoding="utf-8")
    assert "not workflow solutions" in (workspace.root / "TASK_FILES.md").read_text(
        encoding="utf-8"
    )
