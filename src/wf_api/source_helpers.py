from __future__ import annotations

from typing import cast

from pydantic import BaseModel

from wf_core import RuntimeContext

from .platform_context import WorkflowPlatformContext
from .source_refs import SourceResourceRef


class ReadResourceOutput(BaseModel):
    """Bounded resource read result suitable for workflow state/output."""

    source_id: str
    uri: str
    mime_type: str | None = None
    text: str | None = None
    content_count: int
    truncated: bool = False


async def read_resource(
    ref: SourceResourceRef,
    ctx: RuntimeContext,
    *,
    max_chars: int = 4000,
) -> ReadResourceOutput:
    """Explicitly dereference one source resource ref through platform context."""
    platform = ctx.platform
    if platform is None:
        raise RuntimeError("wf.source.read_resource requires platform context")
    typed_platform = cast(WorkflowPlatformContext, platform)
    source_id = typed_platform.resolve_source(ref.logical_source)
    payload = await typed_platform.read_resource(
        source_id=source_id,
        uri=ref.uri,
        max_chars=max_chars,
    )
    contents = payload.get("contents", [])
    first = contents[0] if isinstance(contents, list) and contents else {}
    text = first.get("text") if isinstance(first, dict) else None
    upstream_truncated = payload.get("truncated") is True
    truncated = upstream_truncated or (isinstance(text, str) and len(text) > max_chars)
    if isinstance(text, str) and len(text) > max_chars:
        text = text[:max_chars]
    mime_type: str | None = None
    if isinstance(first, dict) and isinstance(first.get("mimeType"), str):
        mime_type = first["mimeType"]
    elif ref.mime_type is not None:
        mime_type = ref.mime_type
    return ReadResourceOutput(
        source_id=source_id,
        uri=ref.uri,
        mime_type=mime_type,
        text=text if isinstance(text, str) else None,
        content_count=len(contents) if isinstance(contents, list) else 0,
        truncated=truncated,
    )
