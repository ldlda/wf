from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..models import BrokerConfig
from .models import BrokerConfigFile, ConnectionConfigFile


class ConfigMutationError(ValueError):
    """Raised when a requested config mutation cannot be applied."""


class BrokerConfigManager:
    def __init__(self, config_path: str | Path) -> None:
        self.config_path = Path(config_path)

    def load_file(self) -> BrokerConfigFile:
        data = json.loads(self.config_path.read_text(encoding="utf-8"))
        return BrokerConfigFile.model_validate(data)

    def load_runtime(self) -> BrokerConfig:
        return self.load_file().to_runtime(config_path=self.config_path)

    def write_file(self, config: BrokerConfigFile) -> None:
        payload = config.model_dump(mode="json", exclude_none=True)
        text = json.dumps(payload, indent=2) + "\n"
        self.config_path.write_text(text, encoding="utf-8")

    def get_payload(self) -> dict[str, Any]:
        return self.load_file().model_dump(mode="json", exclude_none=True)

    def add_connection(
        self,
        *,
        connection_id: str,
        server: str,
        account: str,
        metadata: dict[str, Any] | None = None,
        enabled: bool = True,
    ) -> dict[str, Any]:
        config = self.load_file()
        if _find_connection(config, connection_id) is not None:
            raise ConfigMutationError(f"connection {connection_id!r} already exists")
        connection = ConnectionConfigFile(
            id=connection_id,
            server=server,
            account=account,
            enabled=enabled,
            metadata={} if metadata is None else metadata,
        )
        config.connections.append(connection)
        self.write_file(config)
        return _mutation_payload("add_connection", connection_id)

    def update_connection(
        self,
        *,
        connection_id: str,
        server: str | None = None,
        account: str | None = None,
        metadata: dict[str, Any] | None = None,
        enabled: bool | None = None,
    ) -> dict[str, Any]:
        config = self.load_file()
        index = _find_connection_index(config, connection_id)
        if index is None:
            raise ConfigMutationError(f"connection {connection_id!r} does not exist")
        existing = config.connections[index]
        config.connections[index] = ConnectionConfigFile(
            id=existing.id,
            server=existing.server if server is None else server,
            account=existing.account if account is None else account,
            enabled=existing.enabled if enabled is None else enabled,
            metadata=existing.metadata if metadata is None else metadata,
        )
        self.write_file(config)
        return _mutation_payload("update_connection", connection_id)

    def set_connection_enabled(
        self,
        connection_id: str,
        *,
        enabled: bool,
    ) -> dict[str, Any]:
        return self.update_connection(connection_id=connection_id, enabled=enabled)

    def remove_connection(self, connection_id: str) -> dict[str, Any]:
        config = self.load_file()
        index = _find_connection_index(config, connection_id)
        if index is None:
            raise ConfigMutationError(f"connection {connection_id!r} does not exist")
        del config.connections[index]
        self.write_file(config)
        return _mutation_payload("remove_connection", connection_id)


def _find_connection(
    config: BrokerConfigFile,
    connection_id: str,
) -> ConnectionConfigFile | None:
    index = _find_connection_index(config, connection_id)
    if index is None:
        return None
    return config.connections[index]


def _find_connection_index(
    config: BrokerConfigFile,
    connection_id: str,
) -> int | None:
    for index, connection in enumerate(config.connections):
        if connection.id == connection_id:
            return index
    return None


def _mutation_payload(action: str, connection_id: str) -> dict[str, Any]:
    return {
        "action": action,
        "connection_id": connection_id,
        "ok": True,
        "requires_reload": True,
    }
