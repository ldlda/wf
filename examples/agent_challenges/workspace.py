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
    return (
        model.replace("/", "_").replace("\\", "_").replace(":", "_").replace("..", "_")
    )


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


@dataclass(frozen=True, slots=True)
class V2TrialWorkspace:
    root: Path
    config_path: Path
    rendered_prompt_path: Path
    instruction_files: tuple[Path, ...]


def _load_instruction_bundle(
    bundle_path: Path,
) -> list[tuple[str, str]]:
    import yaml

    loaded = yaml.safe_load(bundle_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict) or not isinstance(loaded.get("files"), list):
        raise ValueError(f"invalid instruction bundle: {bundle_path}")
    entries: list[tuple[str, str]] = []
    project_root = PROJECT_ROOT.resolve()
    for entry in loaded["files"]:
        if not isinstance(entry, dict):
            raise ValueError(f"invalid bundle entry: {entry}")
        source = entry.get("source")
        destination = entry.get("destination")
        if not isinstance(source, str) or not isinstance(destination, str):
            raise ValueError(f"bundle entry missing source/destination: {entry}")
        source_path = Path(source)
        destination_path = Path(destination)
        if source_path.is_absolute() or destination_path.is_absolute():
            raise ValueError(f"bundle paths must be relative: {entry}")
        resolved_source = (project_root / source_path).resolve()
        resolved_destination = (
            project_root / ".agent" / "skills" / destination_path
        ).resolve()
        trusted_destination_root = (project_root / ".agent" / "skills").resolve()
        if not resolved_source.is_relative_to(project_root):
            raise ValueError(f"bundle source escapes project root: {source}")
        if not resolved_destination.is_relative_to(trusted_destination_root):
            raise ValueError(f"bundle destination escapes skill root: {destination}")
        entries.append((source, destination))
    return entries


def prepare_v2_trial_workspace(
    challenge: object,
    *,
    profile: object,
    model: str,
    index: int,
    workspaces_dir: Path,
    instruction_bundle: Path,
) -> V2TrialWorkspace:
    from .models import InstructionProfile, LoadedChallenge

    if not isinstance(challenge, LoadedChallenge):
        raise TypeError("challenge must be a LoadedChallenge")
    if not isinstance(profile, InstructionProfile):
        raise TypeError("profile must be an InstructionProfile")

    root = workspaces_dir / f"{_safe_model_name(model)}-trial-{index:03d}"
    if root.exists():
        raise FileExistsError(f"trial workspace already exists: {root}")

    shutil.copytree(challenge.workspace_template, root)

    config_path = root / "wf.config.json"
    relative_source = Path(
        os.path.relpath(challenge.source_root, config_path.parent)
    ).as_posix()
    config = {
        "version": 1,
        "client": {"target": {"kind": "local"}},
        "server": {
            "store": {"kind": "filesystem", "root": challenge.manifest.store_root},
            "sources": [
                {
                    "kind": "python",
                    "id": challenge.manifest.source.id,
                    "path": relative_source,
                    "module": challenge.manifest.source.module,
                    "registry": challenge.manifest.source.registry,
                }
            ],
        },
    }
    config_path.write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    instruction_files: list[Path] = []
    if profile in (
        InstructionProfile.SKILLS,
        InstructionProfile.ALL,
        InstructionProfile.DEBUG,
    ):
        bundle_entries = _load_instruction_bundle(instruction_bundle)
        for source_rel, destination_rel in bundle_entries:
            source_file = PROJECT_ROOT / source_rel
            dest_file = root / ".agent" / "skills" / destination_rel
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, dest_file)
            instruction_files.append(dest_file)

    rendered_prompt_path = root / "rendered-prompt.md"
    return V2TrialWorkspace(
        root=root,
        config_path=config_path,
        rendered_prompt_path=rendered_prompt_path,
        instruction_files=tuple(instruction_files),
    )
