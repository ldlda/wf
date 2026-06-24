from __future__ import annotations

from pathlib import Path

import yaml

from .models import ChallengeManifest, LoadedChallenge


def _inside(
    root: Path, relative: str, *, field: str, boundary: Path | None = None
) -> Path:
    candidate = (root / relative).resolve()
    allowed_root = (boundary or root).resolve()
    if not candidate.is_relative_to(allowed_root):
        raise ValueError(f"challenge {field} must stay inside challenge directory")
    return candidate


def _source_boundary(root: Path) -> Path:
    """Real challenge bundles may point at sibling example source directories."""
    if root.parent.name == "agent_challenges":
        return root.parent.parent
    return root


def load_challenge_manifest(path: Path) -> LoadedChallenge:
    manifest_path = path.resolve()
    root = manifest_path.parent
    loaded = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest = ChallengeManifest.model_validate(loaded)
    prompt_path = _inside(root, manifest.prompt, field="prompt")
    workspace_template = _inside(
        root, manifest.workspace_template, field="workspace_template"
    )
    source_root = _inside(
        root,
        manifest.source.root,
        field="source.root",
        boundary=_source_boundary(root),
    )
    server_config = _inside(
        root,
        manifest.server.config,
        field="server.config",
        boundary=_source_boundary(root),
    )
    if not prompt_path.is_file():
        raise ValueError(f"challenge prompt does not exist: {prompt_path}")
    if not workspace_template.is_dir():
        raise ValueError(
            f"challenge workspace_template does not exist: {workspace_template}"
        )
    return LoadedChallenge(
        manifest_path=manifest_path,
        root=root,
        prompt_path=prompt_path,
        workspace_template=workspace_template,
        source_root=source_root,
        server_config=server_config,
        manifest=manifest,
    )
