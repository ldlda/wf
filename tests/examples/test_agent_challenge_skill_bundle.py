from __future__ import annotations

import shutil
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = (
    ROOT / "examples" / "agent_challenges" / "instruction_bundles" / "workflow_cli.yaml"
)


def _bundle() -> dict[str, object]:
    loaded = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _entries() -> list[dict[str, str]]:
    raw = _bundle()["files"]
    assert isinstance(raw, list)
    entries: list[dict[str, str]] = []
    for value in raw:
        assert isinstance(value, dict)
        assert isinstance(value.get("source"), str)
        assert isinstance(value.get("destination"), str)
        entries.append(value)
    return entries


def test_workflow_cli_bundle_has_unique_existing_files() -> None:
    bundle = _bundle()
    entries = _entries()

    assert bundle["version"] == 1
    assert bundle["id"] == "workflow-cli"
    assert len(entries) >= 8
    sources = [entry["source"] for entry in entries]
    destinations = [entry["destination"] for entry in entries]
    assert len(sources) == len(set(sources))
    assert len(destinations) == len(set(destinations))
    assert all((ROOT / source).is_file() for source in sources)
    assert all(not Path(destination).is_absolute() for destination in destinations)
    assert all(".." not in Path(destination).parts for destination in destinations)


def test_workflow_cli_bundle_uses_public_surfaces_not_implementation_files() -> None:
    contents = "\n".join(
        (ROOT / entry["source"]).read_text(encoding="utf-8") for entry in _entries()
    )

    assert "tests/" not in contents
    assert "src/" not in contents
    assert "test_" not in contents
    assert "wf schema" in contents
    assert "wf draft validate" in contents
    assert "wf deploy validate" in contents
    assert "wf run trace" in contents
    assert "empty command group" not in contents
    assert "no schema subcommands" not in contents


def test_workflow_cli_bundle_uses_cli_names_not_mcp_method_names() -> None:
    contents = "\n".join(
        (ROOT / entry["source"]).read_text(encoding="utf-8") for entry in _entries()
    )

    assert "wf.workflow." not in contents
    assert "wf.admin." not in contents
    assert "WorkflowApi." not in contents


def test_workflow_cli_bundle_avoids_challenge_specific_names() -> None:
    contents = "\n".join(
        (ROOT / entry["source"]).read_text(encoding="utf-8") for entry in _entries()
    )

    forbidden = [
        "browser_click",
        "report_workflow",
        "report_case_study",
        "local.report",
        "read_notes",
        "extract_report",
        "render_markdown_report",
    ]
    for term in forbidden:
        assert term not in contents


def test_bundle_destinations_form_two_skills() -> None:
    destinations = {entry["destination"] for entry in _entries()}

    assert "wf-cli/SKILL.md" in destinations
    assert "wf-workflow/SKILL.md" in destinations
    assert any(path.startswith("wf-workflow/references/") for path in destinations)


def test_workflow_cli_bundle_copies_to_agent_skill_root(tmp_path: Path) -> None:
    destination_root = tmp_path / ".agent" / "skills"
    for entry in _entries():
        source = ROOT / entry["source"]
        destination = destination_root / entry["destination"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    assert (destination_root / "wf-cli" / "SKILL.md").is_file()
    assert (destination_root / "wf-workflow" / "SKILL.md").is_file()
    assert (
        destination_root / "wf-workflow" / "references" / "direct-plan-import.md"
    ).is_file()
