from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from wf_mcp.events import McpEvent, make_event

from .connection_service import ConnectionService
from .source_catalog import SourceCatalogService
from .upstream_transport import UpstreamTransportService

EventSink = Callable[[McpEvent], None]


@dataclass(slots=True)
class ContentAccessService:
    """Own local-docs-aware resource reads and prompt renders for the broker.

    This service checks SourceCatalogService for local documentation entries
    before falling back to upstream transport. It is broker-internal, not a
    protocol-neutral content API.
    """

    source_catalog: SourceCatalogService
    upstream: UpstreamTransportService
    connection_service: ConnectionService
    event_sink: EventSink

    async def read_resource(self, qualified_name: str) -> dict[str, Any]:
        local_resource = self.source_catalog.local_documentation_resource(
            qualified_name
        )
        if local_resource is not None:
            self.event_sink(
                make_event(
                    "resource_read_completed",
                    capability_id=qualified_name,
                    payload={"uri": local_resource.uri, "source": "local"},
                )
            )
            return {
                "contents": [
                    {
                        "uri": local_resource.uri,
                        "mimeType": local_resource.mime_type,
                        "text": local_resource.text,
                    }
                ]
            }

        resource = self.source_catalog.get_resource(qualified_name)
        connection = self.connection_service.get(resource.connection_id)
        return await self.upstream.read_resource(
            connection,
            qualified_name,
            resource.uri,
        )

    async def render_prompt(
        self,
        qualified_name: str,
        *,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        local_prompt = self.source_catalog.local_documentation_prompt(qualified_name)
        if local_prompt is not None:
            self.event_sink(
                make_event(
                    "prompt_get_completed",
                    capability_id=qualified_name,
                    payload={
                        "argument_keys": sorted((arguments or {}).keys()),
                        "source": "local",
                    },
                )
            )
            return {
                "description": local_prompt.description,
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": local_prompt.text,
                        },
                    }
                ],
            }

        prompt = self.source_catalog.get_prompt(qualified_name)
        connection = self.connection_service.get(prompt.connection_id)
        return await self.upstream.render_prompt(
            connection,
            qualified_name,
            prompt.local_name,
            arguments,
        )
