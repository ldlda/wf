from __future__ import annotations

from wf_api.wrapper_hints import wrapper_hints_for_capability


def test_wrapper_hints_only_auto_bind_required_inputs() -> None:
    hints = wrapper_hints_for_capability(
        capability_name="local.report.read_notes",
        input_schema={
            "type": "object",
            "required": ["text"],
            "properties": {
                "text": {"type": "string"},
                "path": {"type": "string"},
            },
        },
        output_schema={
            "type": "object",
            "properties": {"notes": {"type": "string"}},
            "required": ["notes"],
        },
        outcomes=["ok"],
    ).model_dump(mode="json")

    assert hints["input_map"] == {"input.text": "text"}
    assert any("path" in note for note in hints["notes"])
