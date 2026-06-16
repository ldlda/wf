from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class ChallengeDef:
    name: str
    source_root: Path
    source_id: str
    source_module: str
    source_registry: str
    store_root: str
    default_workspace_template: Path
    default_workspaces_dir: Path
    default_results_dir: Path
    default_prompt: Path
    default_server_port: int
    server_config_arg: str


@dataclass(frozen=True, slots=True)
class TrialConfig:
    model: str
    variant: str
    prompt_path: Path
    attach_url: str | None
    timeout_seconds: int
    wf_command_prefix: str
    server_context: str


@dataclass(frozen=True, slots=True)
class TrialWorkspace:
    root: Path
    config_path: Path
    prompt_path: Path


def render_prompt(
    prompt_path: Path,
    *,
    wf_command_prefix: str,
    server_context: str,
) -> str:
    return (
        prompt_path.read_text(encoding="utf-8")
        .replace("{{wf_command_prefix}}", wf_command_prefix)
        .replace("{{server_context}}", server_context)
    )


def rpc_url_for_port(port: int) -> str:
    return f"http://127.0.0.1:{port}/rpc"


def server_command(*, port: int, config_arg: str) -> list[str]:
    return [
        "uv",
        "run",
        "wf-rpc-server",
        "--config",
        config_arg,
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]


def _safe_model_name(model: str) -> str:
    return model.replace("/", "_").replace(":", "_")


def prepare_trial_workspace(
    defn: ChallengeDef,
    *,
    model: str,
    index: int,
    workspaces_dir: Path | None = None,
    template_dir: Path | None = None,
    source_root: Path | None = None,
) -> TrialWorkspace:
    if workspaces_dir is None:
        workspaces_dir = defn.default_workspaces_dir
    if template_dir is None:
        template_dir = defn.default_workspace_template
    effective_source_root = source_root if source_root is not None else defn.source_root
    root = workspaces_dir / f"{_safe_model_name(model)}-trial-{index:03d}"
    if root.exists():
        raise FileExistsError(f"trial workspace already exists: {root}")
    shutil.copytree(template_dir, root)
    workspace = TrialWorkspace(
        root=root,
        config_path=root / "wf.config.json",
        prompt_path=root / "prompt.md",
    )
    write_trial_config(
        workspace.config_path, defn=defn, source_root=effective_source_root
    )
    return workspace


def write_trial_config(
    config_path: Path,
    *,
    defn: ChallengeDef,
    source_root: Path | None = None,
) -> None:
    effective_source_root = source_root if source_root is not None else defn.source_root
    relative_source = Path(
        os.path.relpath(effective_source_root, config_path.parent)
    ).as_posix()
    config = {
        "version": 1,
        "client": {"target": {"kind": "local"}},
        "server": {
            "store": {"kind": "filesystem", "root": defn.store_root},
            "sources": [
                {
                    "kind": "python",
                    "id": defn.source_id,
                    "path": relative_source,
                    "module": defn.source_module,
                    "registry": defn.source_registry,
                }
            ],
        },
    }
    config_path.write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def wf_command_prefix_for_config(config_path: Path) -> str:
    path = config_path
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    try:
        path_arg = path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        path_arg = str(path.resolve())
    return f"uv run wf --config {path_arg} --local"


def _trial_index_from_name(name: str, *, safe_model: str) -> int | None:
    prefix = f"{safe_model}-trial-"
    if not name.startswith(prefix):
        return None
    suffix = name.removeprefix(prefix)
    if "." in suffix:
        suffix = suffix.split(".", 1)[0]
    if not suffix.isdigit():
        return None
    return int(suffix)


def starting_trial_index(
    *,
    model: str,
    results_dir: Path,
    workspaces_dir: Path,
) -> int:
    safe_model = _safe_model_name(model)
    highest = 0
    for directory in (results_dir, workspaces_dir):
        if not directory.exists():
            continue
        for path in directory.iterdir():
            index = _trial_index_from_name(path.name, safe_model=safe_model)
            if index is not None:
                highest = max(highest, index)
    return highest + 1


def trial_output_path(results_dir: Path, *, model: str, index: int) -> Path:
    return results_dir / f"{_safe_model_name(model)}-trial-{index:03d}.json"


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())
