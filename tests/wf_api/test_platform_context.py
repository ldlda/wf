from __future__ import annotations

import pytest

from wf_api.platform_context import SourceBindingPlatformContext


def test_platform_context_resolves_logical_source() -> None:
    context = SourceBindingPlatformContext(
        source_bindings={"drive": "drive.personal"},
        read_resource_handler=None,
    )

    assert context.resolve_source("drive") == "drive.personal"


def test_platform_context_uses_identity_for_platform_sources() -> None:
    context = SourceBindingPlatformContext(
        source_bindings={},
        platform_sources={"wf.source"},
        read_resource_handler=None,
    )

    assert context.resolve_source("wf.source") == "wf.source"


def test_platform_context_rejects_unbound_source() -> None:
    context = SourceBindingPlatformContext(
        source_bindings={}, read_resource_handler=None
    )

    with pytest.raises(KeyError, match="unbound logical source"):
        context.resolve_source("drive")
