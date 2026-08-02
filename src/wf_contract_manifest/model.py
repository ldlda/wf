from __future__ import annotations

from typing import TypedDict

type JsonScalar = None | bool | int | float | str
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type JsonSchema = dict[str, JsonValue]


class ManifestSource(TypedDict):
    format: str
    openrpc_version: str


class ManifestParameter(TypedDict):
    name: str
    required: bool
    schema: JsonSchema


class ManifestResult(TypedDict):
    schema: JsonSchema


class ManifestOperation(TypedDict):
    method: str
    namespace: list[str]
    action: str
    params: list[ManifestParameter]
    result: ManifestResult
    errors: list[JsonSchema]


class ManifestComponents(TypedDict):
    schemas: dict[str, JsonSchema]
    errors: dict[str, JsonValue]


class ContractManifest(TypedDict):
    manifest_version: int
    source: ManifestSource
    operations: list[ManifestOperation]
    components: ManifestComponents


class ManifestError(ValueError):
    """Report an invalid source contract with its exact OpenRPC document path."""

    def __init__(self, path: str, message: str) -> None:
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message}")
