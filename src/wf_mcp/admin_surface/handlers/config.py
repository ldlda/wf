from typing import Any, Protocol


class ConfigManager(Protocol):
    """Config mutation methods used by transparent admin handlers."""

    def get_payload(self) -> dict[str, Any]: ...

    def add_connection(
        self,
        *,
        connection_id: str,
        server: str,
        account: str,
        metadata: dict[str, Any] | None = None,
        enabled: bool = True,
    ) -> dict[str, Any]: ...

    def update_connection(
        self,
        *,
        connection_id: str,
        server: str | None = None,
        account: str | None = None,
        metadata: dict[str, Any] | None = None,
        enabled: bool | None = None,
    ) -> dict[str, Any]: ...

    def set_connection_enabled(
        self,
        connection_id: str,
        *,
        enabled: bool,
    ) -> dict[str, Any]: ...

    def remove_connection(self, connection_id: str) -> dict[str, Any]: ...
