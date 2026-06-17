from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def markdown_links(text: str) -> set[str]:
    """Return inline Markdown link hrefs from docs smoke-test files."""
    return set(re.findall(r"(?<!!)\[[^\]]+\]\(([^)]+)\)", text))


def test_big_doc_links_case_study_and_embeds_evidence_index() -> None:
    doc = (ROOT / "docs" / "add" / "system-design-implementation.md").read_text(
        encoding="utf-8"
    )
    links = markdown_links(doc)

    assert any(link.startswith("../../examples/report_workflow") for link in links)
    assert "Evidence Index" in doc
    assert "Core Workflow Lifecycle" in doc
    assert "Agent Challenge Evaluation Protocol" in doc


def test_project_map_links_big_doc() -> None:
    project_map = (ROOT / "docs" / "project_map.md").read_text(encoding="utf-8")
    links = markdown_links(project_map)

    assert any(link.endswith("system-design-implementation.md") for link in links)
    assert any(link.endswith("evidence-index.md") for link in links)


def test_big_doc_keeps_mcp_as_source_family() -> None:
    doc = (ROOT / "docs" / "add" / "system-design-implementation.md").read_text(
        encoding="utf-8"
    )

    assert "MCP" in doc
    assert "source family" in doc
    assert "product identity" in doc
