from typing import TYPE_CHECKING

from .io import (
    DEFAULT_MANIFEST_PATH,
    ManifestDriftError,
    canonical_manifest_json,
    check_manifest,
    write_manifest,
)
from .model import ContractManifest, JsonSchema, JsonValue, ManifestError
from .normalize import manifest_from_openrpc

if TYPE_CHECKING:
    from .generate import generate_manifest


def __getattr__(name: str) -> object:
    """Load the server-backed generator only when a caller requests it."""
    if name == "generate_manifest":
        from .generate import generate_manifest

        return generate_manifest
    raise AttributeError(name)

__all__ = [
    "ContractManifest",
    "JsonSchema",
    "JsonValue",
    "ManifestError",
    "manifest_from_openrpc",
    "generate_manifest",
    "DEFAULT_MANIFEST_PATH",
    "ManifestDriftError",
    "canonical_manifest_json",
    "check_manifest",
    "write_manifest",
]
