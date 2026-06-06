from __future__ import annotations

from wf_sources_mcp.catalog import (
    CatalogNodeEntry,
    CatalogPromptEntry,
    CatalogResourceEntry,
    CatalogSnapshot,
    DiscoveredPrompt,
    DiscoveredResource,
    DiscoveredTool,
    dump_catalog_snapshot,
)


def test_discovered_tool_default_outcome_and_metadata() -> None:
    tool = DiscoveredTool(
        name="echo",
        title=None,
        description="Echo input",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )

    assert tool.outcomes == ("ok",)
    assert tool.metadata == {}


def test_discovered_resource_and_prompt_keep_structural_fields() -> None:
    resource = DiscoveredResource(
        uri="docs://guide",
        name="guide",
        title="Guide",
        description="Read me",
        mime_type="text/markdown",
    )
    prompt = DiscoveredPrompt(
        name="summarize",
        title=None,
        description="Summarize",
        arguments=[{"name": "topic"}],
    )

    assert resource.uri == "docs://guide"
    assert resource.mime_type == "text/markdown"
    assert prompt.arguments == [{"name": "topic"}]


def test_catalog_snapshot_staleness_and_dump_shape() -> None:
    snapshot = CatalogSnapshot(
        connection_id="demo.default",
        fetched_at_epoch_ms=1_000,
        max_age_seconds=2,
        nodes=[
            CatalogNodeEntry(
                qualified_name="demo.default.echo",
                connection_id="demo.default",
                local_name="echo",
                title=None,
                description="Echo",
                outcomes=("ok",),
                input_schema={"type": "object"},
                output_schema={"type": "object"},
            )
        ],
        resources=[
            CatalogResourceEntry(
                qualified_name="demo.default.guide",
                connection_id="demo.default",
                local_name="guide",
                title=None,
                uri="docs://guide",
                description="Guide",
            )
        ],
        prompts=[
            CatalogPromptEntry(
                qualified_name="demo.default.summarize",
                connection_id="demo.default",
                local_name="summarize",
                title=None,
                description="Summarize",
            )
        ],
        metadata={"source": "test"},
    )

    assert snapshot.is_stale(3_001) is True
    dumped = dump_catalog_snapshot(snapshot)
    assert dumped["connection_id"] == "demo.default"
    assert dumped["nodes"][0]["qualified_name"] == "demo.default.echo"
    assert dumped["resources"][0]["uri"] == "docs://guide"
    assert dumped["prompts"][0]["local_name"] == "summarize"
    assert dumped["metadata"] == {"source": "test"}
