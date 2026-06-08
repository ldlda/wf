from __future__ import annotations

import dataclasses

from pydantic import BaseModel

from wf_authoring import NodeSpec
from wf_sources_mcp.catalog import (
    CombinedCatalog,
    DiscoveredPrompt,
    DiscoveredResource,
    snapshot_from_specs,
)


class EchoInput(BaseModel):
    message: str


class EchoOutput(BaseModel):
    text: str


async def _echo(payload: EchoInput) -> EchoOutput:
    return EchoOutput(text=payload.message)


def _echo_spec() -> NodeSpec[EchoInput, EchoOutput]:
    return NodeSpec(
        name="echo",
        input_model=EchoInput,
        output_model=EchoOutput,
        outcomes=("ok",),
        fn=_echo,
        description="Echo message",
        is_async=True,
        input_schema_contract={
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
        output_schema_contract={
            "type": "object",
            "properties": {"text": {"type": "string"}},
        },
    )


def test_snapshot_from_specs_qualifies_nodes_resources_and_prompts() -> None:
    snapshot = snapshot_from_specs(
        "demo.default",
        specs={"echo": _echo_spec()},
        tool_display_names={"echo": "Echo Tool"},
        resources=[
            DiscoveredResource(
                uri="demo://docs/guide",
                name="guide",
                title="Guide",
                description="Read me",
                mime_type="text/markdown",
                metadata={"kind": "doc"},
            )
        ],
        prompts=[
            DiscoveredPrompt(
                name="summarize",
                title="Summarize",
                description="Summarize text",
                arguments=[{"name": "topic"}],
                metadata={"kind": "prompt"},
            )
        ],
        metadata={"source": "test"},
        fetched_at_epoch_ms=123,
        max_age_seconds=60,
    )

    assert snapshot.connection_id == "demo.default"
    assert snapshot.nodes[0].qualified_name == "demo.default.echo"
    assert snapshot.nodes[0].local_name == "echo"
    assert snapshot.nodes[0].title == "Echo Tool"
    assert snapshot.resources[0].qualified_name == "demo.default.guide"
    assert snapshot.resources[0].uri == "demo://docs/guide"
    assert snapshot.prompts[0].qualified_name == "demo.default.summarize"
    assert snapshot.prompts[0].arguments == [{"name": "topic"}]
    assert snapshot.metadata == {"source": "test"}


def test_snapshot_from_specs_preserves_already_qualified_node_name() -> None:
    spec = dataclasses.replace(_echo_spec(), name="demo.default.echo")

    snapshot = snapshot_from_specs(
        "demo.default",
        specs={"demo.default.echo": spec},
        fetched_at_epoch_ms=123,
        max_age_seconds=60,
    )

    assert snapshot.nodes[0].qualified_name == "demo.default.echo"
    assert snapshot.nodes[0].local_name == "echo"


def test_combined_catalog_sorts_entries_and_serializes_payload() -> None:
    first = snapshot_from_specs(
        "zeta.default",
        specs={"echo": _echo_spec()},
        resources=[DiscoveredResource(uri="zeta://guide", name="guide", title=None, description=None)],
        prompts=[DiscoveredPrompt(name="prompt", title=None, description=None)],
        metadata={"order": "second"},
        fetched_at_epoch_ms=2,
        max_age_seconds=60,
    )
    second = snapshot_from_specs(
        "alpha.default",
        specs={"echo": _echo_spec()},
        resources=[DiscoveredResource(uri="alpha://guide", name="guide", title=None, description=None)],
        prompts=[DiscoveredPrompt(name="prompt", title=None, description=None)],
        metadata={"order": "first"},
        fetched_at_epoch_ms=1,
        max_age_seconds=60,
    )

    catalog = CombinedCatalog(
        snapshots={
            first.connection_id: first,
            second.connection_id: second,
        }
    )
    payload = catalog.as_payload()

    assert [entry.qualified_name for entry in catalog.entries()] == [
        "alpha.default.echo",
        "zeta.default.echo",
    ]
    assert catalog.find_resource("alpha.default.guide") is not None
    assert catalog.find_prompt("zeta.default.prompt") is not None
    assert [node["qualified_name"] for node in payload["nodes"]] == [
        "alpha.default.echo",
        "zeta.default.echo",
    ]
    assert [item["connection_id"] for item in payload["connections"]] == [
        "alpha.default",
        "zeta.default",
    ]
