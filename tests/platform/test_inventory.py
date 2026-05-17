from __future__ import annotations

from pydantic import BaseModel, Field

from wf_authoring import node
from wf_platform import CapabilityBuckets, CapabilitySource, NodeSpecInventory


class EchoInput(BaseModel):
    text: str = Field(description="Text to echo.")


class EchoOutput(BaseModel):
    echoed: str


@node
def echo(payload: EchoInput) -> EchoOutput:
    """Echo one text field."""
    return EchoOutput(echoed=payload.text)


def test_source_inventory_exposes_serializable_node_spec_details() -> None:
    source = CapabilitySource(
        id="demo.personal",
        kind="connection",
        capabilities=CapabilityBuckets(node_specs={echo.name: echo}),
    )

    inventory = source.as_inventory()
    detail = inventory.capabilities.node_spec_details[0]
    dumped = inventory.model_dump(mode="json")

    assert isinstance(detail, NodeSpecInventory)
    assert detail.name == echo.name
    assert detail.description == "Echo one text field."
    assert detail.outcomes == ("ok",)
    assert detail.input_schema["properties"]["text"]["description"] == "Text to echo."
    assert "fn" not in dumped["capabilities"]["node_spec_details"][0]
