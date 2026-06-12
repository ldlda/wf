from __future__ import annotations

import json
from pathlib import Path

from .models import (
    FilesystemStoreConfig,
    PythonSourceConfig,
    ServerStoresConfig,
    SourceConfig,
    StoreConfig,
    WorkflowConfigFile,
)


def load_workflow_config(path: str | Path) -> WorkflowConfigFile:
    """Load neutral workflow config and resolve local filesystem/source paths.

    Relative filesystem store roots are config-file relative so `wf --config`
    behaves the same regardless of the caller's current working directory.
    Role-specific store overrides and Python source import paths follow the
    same rule.
    """

    config_path = Path(path)
    data = json.loads(config_path.read_text(encoding="utf-8"))
    config = WorkflowConfigFile.model_validate(data)
    return _resolve_store_paths(config, base_dir=config_path.parent)


def _resolve_store_paths(
    config: WorkflowConfigFile,
    *,
    base_dir: Path,
) -> WorkflowConfigFile:
    server = config.server
    resolved_stores = ServerStoresConfig(
        workflow=_resolve_store(server.stores.workflow, base_dir=base_dir),
        auth=_resolve_store(server.stores.auth, base_dir=base_dir),
        source_registry=_resolve_store(
            server.stores.source_registry,
            base_dir=base_dir,
        ),
        catalog_cache=_resolve_store(
            server.stores.catalog_cache,
            base_dir=base_dir,
        ),
    )
    return config.model_copy(
        update={
            "server": server.model_copy(
                update={
                    "store": _resolve_store(server.store, base_dir=base_dir),
                    "stores": resolved_stores,
                    "sources": _resolve_source_paths(
                        server.sources,
                        base_dir=base_dir,
                    ),
                }
            )
        }
    )


def _resolve_store(
    store: StoreConfig | None,
    *,
    base_dir: Path,
) -> StoreConfig | None:
    if isinstance(store, FilesystemStoreConfig) and not store.root.is_absolute():
        return store.model_copy(update={"root": (base_dir / store.root).resolve()})
    return store


def _resolve_source_paths(
    sources: list[SourceConfig],
    *,
    base_dir: Path,
) -> list[SourceConfig]:
    resolved: list[SourceConfig] = []
    for source in sources:
        if isinstance(source, PythonSourceConfig) and not source.path.is_absolute():
            resolved.append(
                source.model_copy(update={"path": (base_dir / source.path).resolve()})
            )
        else:
            resolved.append(source)
    return resolved
