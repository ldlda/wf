from __future__ import annotations

import pytest

from wf_api.platform_context import SourceBindingPlatformContext
from wf_api.source_helpers import read_resource
from wf_api.source_refs import SourceResourceRef
from wf_core import RuntimeContext


async def test_read_resource_resolves_logical_source_and_bounds_text() -> None:
    calls: list[tuple[str, str, int]] = []

    async def handler(source_id: str, uri: str, max_chars: int):
        calls.append((source_id, uri, max_chars))
        return {
            "contents": [
                {
                    "type": "text",
                    "text": "abcdefghijklmnopqrstuvwxyz",
                    "mimeType": "text/plain",
                }
            ]
        }

    platform = SourceBindingPlatformContext(
        source_bindings={"drive": "drive.personal"},
        read_resource_handler=handler,
    )

    result = await read_resource(
        SourceResourceRef(logical_source="drive", uri="gdrive://file/abc"),
        RuntimeContext(current_node_id="read", platform=platform),
        max_chars=5,
    )

    assert calls == [("drive.personal", "gdrive://file/abc", 5)]
    assert result.truncated is True
    assert result.text == "abcde"


async def test_read_resource_requires_platform_context() -> None:
    with pytest.raises(RuntimeError, match="platform context"):
        await read_resource(
            SourceResourceRef(logical_source="drive", uri="gdrive://file/abc"),
            RuntimeContext(current_node_id="read"),
        )
