from __future__ import annotations

import json
from pathlib import Path

from .model import ContractManifest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST_PATH = REPOSITORY_ROOT / "contracts" / "workflow-api.manifest.json"


class ManifestDriftError(RuntimeError):
    """Indicate that the checked manifest differs from the generated contract."""


def canonical_manifest_json(manifest: ContractManifest) -> str:
    try:
        return json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    except (TypeError, ValueError) as error:
        raise ValueError(f"manifest is not canonically serializable: {error}") from error


def write_manifest(
    manifest: ContractManifest, path: Path = DEFAULT_MANIFEST_PATH
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_manifest_json(manifest), encoding="utf-8", newline="\n")
    return path


def check_manifest(
    manifest: ContractManifest, path: Path = DEFAULT_MANIFEST_PATH
) -> None:
    expected = canonical_manifest_json(manifest).encode("utf-8")
    try:
        actual = path.read_bytes()
    except FileNotFoundError as error:
        raise ManifestDriftError(
            f"{path} is missing; run `python -m wf_contract_manifest write`"
        ) from error
    if actual != expected:
        raise ManifestDriftError(
            f"{path} is stale; run `python -m wf_contract_manifest write`"
        )
