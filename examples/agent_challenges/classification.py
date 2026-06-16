from __future__ import annotations

from typing import Any

import yaml


def extract_challenge_report(text: str) -> dict[str, Any] | None:
    marker = "```yaml"
    start = text.lower().rfind(marker)
    if start == -1:
        return None
    body_start = text.find("\n", start)
    if body_start == -1:
        return None
    end = text.find("```", body_start + 1)
    if end == -1:
        return None
    raw_yaml = text[body_start + 1 : end]
    loaded = yaml.safe_load(raw_yaml)
    if not isinstance(loaded, dict):
        return None
    report = loaded.get("challenge_report")
    return report if isinstance(report, dict) else None


def _contains_bool_marker(text: str, marker: str, value: str) -> bool:
    marker_index = text.find(marker)
    if marker_index == -1:
        return False
    return value in text[marker_index : marker_index + 80]
