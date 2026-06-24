from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read_doc(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _markdown_links(text: str) -> set[str]:
    return set(re.findall(r"(?<!!)\[[^\]]+\]\(([^)]+)\)", text))


def test_cli_docs_link_source_provider_guide() -> None:
    text = _read_doc("docs/wf_cli.md")

    assert "source_provider_guide.md" in text
    assert "Source Provider Guide" in text


def test_project_map_links_source_provider_guide() -> None:
    text = _read_doc("docs/project_map.md")

    assert "source_provider_guide.md" in text


def test_source_provider_guide_links_python_runbook() -> None:
    text = _read_doc("docs/source_provider_guide.md")

    assert "runbooks/python-source.md" in text
    assert "wf source diagnose" in text


def test_project_map_links_agent_challenge_runbook() -> None:
    text = _read_doc("docs/project_map.md")

    assert "runbooks/agent-challenge-evaluation.md" in _markdown_links(text)


def test_agent_challenge_readmes_link_shared_runbook() -> None:
    browser = _read_doc("examples/agent_challenges/browser_click_challenge/README.md")
    report = _read_doc("examples/agent_challenges/report_workflow_challenge/README.md")

    assert "../../../docs/runbooks/agent-challenge-evaluation.md" in _markdown_links(
        browser
    )
    assert "../../../docs/runbooks/agent-challenge-evaluation.md" in _markdown_links(
        report
    )


def test_agent_challenge_runbook_defines_validity_and_coverage() -> None:
    text = _read_doc("docs/runbooks/agent-challenge-evaluation.md")

    assert "evaluation_validity" in text
    assert "policy_coverage" in text
    assert "Manual audit is authoritative" in text
