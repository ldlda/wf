from typing import TYPE_CHECKING

from .paging import Page, page_items
from .refs import CapabilityRef, SourceRef
from .schema_hashes import hash_json_schema

if TYPE_CHECKING:
    from .docs import (
        DocumentationPrompt,
        DocumentationResource,
        build_documentation_source,
    )
    from .sources import (
        CapabilityBuckets,
        CapabilitySource,
        NodeSpecInventory,
        ReducerInventory,
        SourceCapabilityInventory,
        SourceInventory,
        SourceKind,
        SourcePermissions,
        SourcePermissionsSnapshot,
        SourcePolicy,
        SourcePolicySnapshot,
        SourceStatus,
        SourceVisibility,
        SourceVisibilitySnapshot,
    )

_LAZY_EXPORTS = {
    "CapabilityBuckets": ".sources",
    "CapabilitySource": ".sources",
    "DocumentationPrompt": ".docs",
    "DocumentationResource": ".docs",
    "NodeSpecInventory": ".sources",
    "ReducerInventory": ".sources",
    "SourceCapabilityInventory": ".sources",
    "SourceInventory": ".sources",
    "SourceKind": ".sources",
    "SourcePermissions": ".sources",
    "SourcePermissionsSnapshot": ".sources",
    "SourcePolicy": ".sources",
    "SourcePolicySnapshot": ".sources",
    "SourceStatus": ".sources",
    "SourceVisibility": ".sources",
    "SourceVisibilitySnapshot": ".sources",
    "build_documentation_source": ".docs",
}

__all__ = [
    "CapabilityBuckets",
    "CapabilitySource",
    "CapabilityRef",
    "DocumentationPrompt",
    "DocumentationResource",
    "NodeSpecInventory",
    "Page",
    "ReducerInventory",
    "SourceCapabilityInventory",
    "SourceInventory",
    "SourceKind",
    "SourcePermissions",
    "SourcePermissionsSnapshot",
    "SourcePolicy",
    "SourcePolicySnapshot",
    "SourceStatus",
    "SourceVisibility",
    "SourceVisibilitySnapshot",
    "SourceRef",
    "build_documentation_source",
    "hash_json_schema",
    "page_items",
]


def __getattr__(name: str) -> object:
    """Load platform inventory exports lazily to keep core-safe refs importable.

    `wf_core` depends on `wf_platform.refs` for structural reducer references.
    Eagerly importing source inventory here would pull in authoring/core again
    and create an import cycle, so only foundational refs/helpers are eager.
    """
    import importlib

    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module 'wf_platform' has no attribute {name!r}")
    module = importlib.import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
