from __future__ import annotations

import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

import wf_contract_manifest.io as manifest_io
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


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_canonical_json_rejects_non_finite_numbers(value: float) -> None:
    manifest = _manifest()
    manifest["components"]["schemas"]["FreeJson"] = {"const": value}

    with pytest.raises(ValueError, match="manifest is not canonically serializable"):
        canonical_manifest_json(manifest)


def test_write_and_check_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "workflow-api.manifest.json"

    assert write_manifest(_manifest(), path) == path
    check_manifest(_manifest(), path)

    assert path.read_bytes() == canonical_manifest_json(_manifest()).encode("utf-8")


def test_default_write_refuses_to_target_a_non_checkout_parent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing_marker = manifest_io.REPOSITORY_ROOT / "missing-pyproject.toml"
    monkeypatch.setattr(manifest_io, "REPOSITORY_MARKER", missing_marker)

    with pytest.raises(RuntimeError, match="repository checkout"):
        write_manifest(_manifest())


def test_check_reports_drift_without_mutating_the_file(tmp_path: Path) -> None:
    path = tmp_path / "workflow-api.manifest.json"
    path.write_text("stale\n", encoding="utf-8")
    before = path.read_bytes()

    with pytest.raises(
        ManifestDriftError, match="python -m wf_contract_manifest write"
    ):
        check_manifest(_manifest(), path)

    assert path.read_bytes() == before
