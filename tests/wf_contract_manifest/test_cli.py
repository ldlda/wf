from __future__ import annotations

from pathlib import Path

import pytest

from wf_contract_manifest import (
    ContractManifest,
    ManifestDriftError,
    manifest_from_openrpc,
)
from wf_contract_manifest.__main__ import main

from .fixtures import synthetic_openrpc_document


def _manifest() -> ContractManifest:
    return manifest_from_openrpc(synthetic_openrpc_document())


def test_write_generates_once_and_writes_requested_contract(monkeypatch, tmp_path: Path) -> None:
    manifest = _manifest()
    calls: list[tuple[object, Path]] = []
    monkeypatch.setattr("wf_contract_manifest.__main__.generate_manifest", lambda: manifest)
    monkeypatch.setattr(
        "wf_contract_manifest.__main__.write_manifest",
        lambda value, path: calls.append((value, path)) or path,
    )
    monkeypatch.setattr("wf_contract_manifest.__main__.DEFAULT_MANIFEST_PATH", tmp_path / "manifest.json")

    assert main(["write"]) == 0
    assert calls == [(manifest, tmp_path / "manifest.json")]


def test_check_returns_nonzero_and_prints_drift_guidance(monkeypatch, capsys) -> None:
    monkeypatch.setattr("wf_contract_manifest.__main__.generate_manifest", _manifest)

    def fail_check(_manifest, _path) -> None:
        raise ManifestDriftError("stale; run `python -m wf_contract_manifest write`")

    monkeypatch.setattr("wf_contract_manifest.__main__.check_manifest", fail_check)

    assert main(["check"]) == 1
    assert "python -m wf_contract_manifest write" in capsys.readouterr().err


def test_rejects_unknown_command() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["unknown"])

    assert exc_info.value.code == 2
