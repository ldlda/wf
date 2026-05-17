from __future__ import annotations

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


def test_capability_ref_rejects_missing_capability_name() -> None:
    try:
        CapabilityRef.parse("demo")
    except ValueError as exc:
        assert "source and capability" in str(exc)
    else:
        raise AssertionError("expected invalid capability ref to be rejected")
