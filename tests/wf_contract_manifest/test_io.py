from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from wf_contract_manifest import (
    ManifestDriftError,
    canonical_manifest_json,
    check_manifest,
    manifest_from_openrpc,
    write_manifest,
)

from .fixtures import synthetic_openrpc_document


def _manifest():
    return manifest_from_openrpc(synthetic_openrpc_document())


def _reverse_mapping_insertions(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: _reverse_mapping_insertions(child)
            for key, child in reversed(list(value.items()))
        }
    if isinstance(value, list):
        return [_reverse_mapping_insertions(item) for item in value]
    return value


def test_canonical_json_is_stable_utf8_text_with_trailing_newline() -> None:
    first = canonical_manifest_json(_manifest())
    second = canonical_manifest_json(_manifest())

    assert first == second
    assert first.endswith("\n")
    assert '  "manifest_version": 1' in first
    assert "\\u" not in first


def test_canonical_json_ignores_recursive_mapping_insertion_order() -> None:
    manifest = _manifest()
    reordered = _reverse_mapping_insertions(manifest)

    assert canonical_manifest_json(manifest).encode("utf-8") == (
        canonical_manifest_json(reordered).encode("utf-8")
    )


def test_write_and_check_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "workflow-api.manifest.json"

    assert write_manifest(_manifest(), path) == path
    check_manifest(_manifest(), path)

    assert path.read_bytes() == canonical_manifest_json(_manifest()).encode("utf-8")


def test_check_reports_drift_without_mutating_the_file(tmp_path: Path) -> None:
    path = tmp_path / "workflow-api.manifest.json"
    path.write_text("stale\n", encoding="utf-8")
    before = path.read_bytes()

    with pytest.raises(
        ManifestDriftError, match="python -m wf_contract_manifest write"
    ):
        check_manifest(_manifest(), path)

    assert path.read_bytes() == before
