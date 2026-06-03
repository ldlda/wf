from __future__ import annotations

import json
from pathlib import Path

from .models import FilesystemStoreConfig, WorkflowConfigFile


def load_workflow_config(path: str | Path) -> WorkflowConfigFile:
    """Load neutral workflow config and resolve local filesystem paths.

    Relative filesystem store roots are config-file relative so `wf --config`
    behaves the same regardless of the caller's current working directory.
    """

    config_path = Path(path)
    data = json.loads(config_path.read_text(encoding="utf-8"))
    config = WorkflowConfigFile.model_validate(data)
    store = config.server.store
    if isinstance(store, FilesystemStoreConfig) and not store.root.is_absolute():
        config = config.model_copy(
            update={
                "server": config.server.model_copy(
                    update={
                        "store": store.model_copy(
                            update={"root": (config_path.parent / store.root).resolve()}
                        )
                    }
                )
            }
        )
    return config
