from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def markdown_links(text: str) -> set[str]:
    """Return inline Markdown link hrefs from docs smoke-test files."""
    return set(re.findall(r"(?<!!)\[[^\]]+\]\(([^)]+)\)", text))


def test_big_doc_links_case_study_and_embeds_evidence_index() -> None:
    doc = (ROOT / "docs" / "thesis" / "system-design-implementation.md").read_text(
        encoding="utf-8"
    )
    links = markdown_links(doc)

    assert any(link.startswith("../../examples/report_workflow") for link in links)
    assert re.search(r"^# Evidence Index$", doc, flags=re.MULTILINE)
    assert re.search(r"^## Core Workflow Lifecycle$", doc, flags=re.MULTILINE)
    assert re.search(
        r"^## Agent Challenge Evaluation Protocol$", doc, flags=re.MULTILINE
    )


def test_project_map_links_big_doc() -> None:
    project_map = (ROOT / "docs" / "project_map.md").read_text(encoding="utf-8")
    links = markdown_links(project_map)

    assert any(link.endswith("system-design-implementation.md") for link in links)
    assert any(link.endswith("evidence-index.md") for link in links)


def test_big_doc_keeps_mcp_as_source_family() -> None:
    doc = (ROOT / "docs" / "thesis" / "system-design-implementation.md").read_text(
        encoding="utf-8"
    )

    assert "MCP" in doc
    assert "source family" in doc
    assert "product identity" in doc


def test_thesis_has_no_placeholder_author_and_keeps_appendix_evidence_together() -> (
    None
):
    doc = (ROOT / "docs" / "thesis" / "system-design-implementation.md").read_text(
        encoding="utf-8"
    )
    appendix = doc.split("# Agent Challenge Harness", maxsplit=1)[1]
    figure = appendix.index("#fig:agent-challenge-audit")
    evidence = appendix.index("Evidence:")
    page_break = appendix.index("\\clearpage")

    assert 'author: "draft"' not in doc
    assert "This draft includes" not in doc
    assert page_break < evidence < figure
    assert figure > evidence
    assert 'latex-placement="H"' in appendix[figure : figure + 300]


def test_thesis_bundle_has_reproducible_agent_evaluation_assets() -> None:
    thesis = ROOT / "docs" / "thesis"
    doc = (thesis / "system-design-implementation.md").read_text(encoding="utf-8")
    results = (thesis / "agent-challenge-results.md").read_text(encoding="utf-8")
    generate_script = (thesis / "generate.ps1").read_text(encoding="utf-8")
    combined_build_script = (thesis / "gengen.ps1").read_text(encoding="utf-8")
    figure_stems = (
        "agent-challenge-audited-outcomes-by-cell",
        "agent-challenge-automatic-vs-manual-outcomes",
        "agent-challenge-longitudinal-outcomes",
        "agent-challenge-duration",
        "agent-challenge-token-volume",
    )

    assert (thesis / "agent-challenge-cohort.json").is_file()
    assert (thesis / "agent-challenge-results.md").is_file()
    assert "include-agent-challenge-results" in doc
    assert "include-markdown.lua" in generate_script
    assert "figure-format.lua" in generate_script
    assert "thesisFigureFormat" in generate_script
    assert (
        generate_script.index("$include_markdown_filter `")
        < generate_script.index("$diagram_filter `")
        < generate_script.index("--filter=pandoc-crossref")
    )
    assert "generate_agent_challenge_evaluation.py" in combined_build_script
    assert "--resource-path" in combined_build_script
    for stem in figure_stems:
        assert f"figures/{stem}.svg" in results
        assert (thesis / "figures" / f"{stem}.svg").is_file()
        assert (thesis / "figures" / f"{stem}.pdf").is_file()


@pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc is not installed")
def test_thesis_lua_filters_include_results_before_rewriting_figures(
    tmp_path: Path,
) -> None:
    thesis = ROOT / "docs" / "thesis"
    source = tmp_path / "source.md"
    included = tmp_path / "included.md"
    source.write_text("::: {#include-agent-challenge-results}\n:::\n", encoding="utf-8")
    included.write_text(
        "## Included result\n\n![Result](figures/result.svg)\n", encoding="utf-8"
    )

    completed = subprocess.run(
        [
            "pandoc",
            str(source),
            "--lua-filter",
            str(thesis / "include-markdown.lua"),
            "--lua-filter",
            str(thesis / "figure-format.lua"),
            "--metadata",
            f"thesisAgentResults={included}",
            "--metadata",
            "thesisFigureFormat=pdf",
            "--to",
            "json",
        ],
        capture_output=True,
        check=False,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0, completed.stderr
    document = json.loads(completed.stdout)
    assert document["blocks"][0]["t"] == "Header"

    def image_targets(value: object) -> list[str]:
        if isinstance(value, dict):
            if value.get("t") == "Image":
                content = value.get("c")
                if isinstance(content, list):
                    return [content[2][0]]
            return [target for item in value.values() for target in image_targets(item)]
        if isinstance(value, list):
            return [target for item in value for target in image_targets(item)]
        return []

    assert image_targets(document) == ["figures/result.pdf"]
