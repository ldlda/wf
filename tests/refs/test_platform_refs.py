from __future__ import annotations

from pydantic import BaseModel

from wf_platform import CapabilityRef, SourceRef


def test_source_ref_round_trips_segmented_names() -> None:
    source = SourceRef.parse("demo.personal")

    assert source.parts == ("demo", "personal")
    assert str(source) == "demo.personal"


def test_capability_ref_round_trips_segmented_names() -> None:
    ref = CapabilityRef.parse("demo.personal.echo_tool")

    assert ref.source.parts == ("demo", "personal")
    assert ref.name == "echo_tool"
    assert str(ref) == "demo.personal.echo_tool"


def test_capability_ref_binds_logical_source_to_concrete_source() -> None:
    ref = CapabilityRef.parse("demo.echo_tool")

    bound = ref.bind({"demo": "demo.personal"})

    assert str(bound) == "demo.personal.echo_tool"


def test_platform_refs_validate_and_serialize_through_pydantic() -> None:
    class Payload(BaseModel):
        source: SourceRef
        capability: CapabilityRef

    payload = Payload.model_validate({
        "source": "demo.personal",
        "capability": "demo.personal.echo_tool",
    })

    assert payload.source == SourceRef.parse("demo.personal")
    assert payload.capability == CapabilityRef.parse("demo.personal.echo_tool")
    assert payload.model_dump(mode="json") == {
        "source": "demo.personal",
        "capability": "demo.personal.echo_tool",
    }


def test_source_ref_rejects_whitespace_segments() -> None:
    try:
        SourceRef.parse("demo. .personal")
    except ValueError as exc:
        assert "non-empty path segments" in str(exc)
    else:
        raise AssertionError("expected whitespace source segment to fail")


def test_capability_ref_rejects_missing_capability_name() -> None:
    try:
        CapabilityRef.parse("demo")
    except ValueError as exc:
        assert "source and capability" in str(exc)
    else:
        raise AssertionError("expected invalid capability ref to be rejected")
