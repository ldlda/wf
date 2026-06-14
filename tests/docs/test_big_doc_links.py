from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_big_doc_links_case_study_and_evidence_index() -> None:
    doc = (ROOT / "docs" / "add" / "system-design-implementation.md").read_text(
        encoding="utf-8"
    )

    assert "examples/report_workflow" in doc
    assert "docs/add/evidence-index.md" in doc or "evidence-index.md" in doc


def test_project_map_links_big_doc() -> None:
    project_map = (ROOT / "docs" / "project_map.md").read_text(encoding="utf-8")

    assert "system-design-implementation.md" in project_map
    assert "evidence-index.md" in project_map


def test_big_doc_keeps_mcp_as_source_family() -> None:
    doc = (ROOT / "docs" / "add" / "system-design-implementation.md").read_text(
        encoding="utf-8"
    )

    assert "MCP" in doc
    assert "source family" in doc
    assert "product identity" in doc
