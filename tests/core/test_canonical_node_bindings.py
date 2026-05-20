import pytest
from pydantic import ValidationError

from wf_core.models.steps import InputPathBinding, InputValueBinding, NodeUse
from wf_core.paths import GraphSourcePath, LocalPath, StatePath


def test_node_use_accepts_canonical_input_and_output_bindings():
    node = NodeUse.model_validate({
        "id": "echo",
        "type": "node",
        "node": "echo",
        "input": [
            {"target": "message", "path": "input.message"},
            {"target": "mode", "value": None},
        ],
        "output": [{"source": "echoed", "target": "state.echoed"}],
    })

    path_binding = node.input[0]
    assert isinstance(path_binding, InputPathBinding)
    assert path_binding.target == LocalPath.of("message")
    assert path_binding.path == GraphSourcePath.input("message")

    value_binding = node.input[1]
    assert isinstance(value_binding, InputValueBinding)
    assert value_binding.target == LocalPath.of("mode")
    assert value_binding.value is None

    assert node.output[0].source == LocalPath.of("echoed")
    assert node.output[0].target == StatePath.of("echoed")


def test_node_use_converts_old_maps_to_canonical_bindings():
    node = NodeUse.model_validate({
        "id": "echo",
        "type": "node",
        "node": "echo",
        "in_map": {"input.message": "message"},
        "input_values": {"mode": "fast"},
        "out_map": {"echoed": "state.echoed"},
    })

    dumped = node.model_dump(mode="json")
    assert "in_map" not in dumped
    assert "input_values" not in dumped
    assert "out_map" not in dumped
    assert dumped["input"][0]["value"] == "fast"
    assert dumped["input"][0]["target"] == "mode"
    assert dumped["input"][1]["path"] == "input.message"
    assert dumped["input"][1]["target"] == "message"
    assert dumped["output"][0]["source"] == "echoed"
    assert dumped["output"][0]["target"] == "state.echoed"


def test_node_use_serializes_canonical_binding_paths_as_strings_in_all_dump_modes():
    node = NodeUse.model_validate({
        "id": "echo",
        "type": "node",
        "node": "echo",
        "input": [{"target": "message", "path": "input.message"}],
        "output": [{"source": "echoed", "target": "state.echoed"}],
    })

    python_dumped = node.model_dump()
    json_dumped = node.model_dump(mode="json")

    assert python_dumped["input"][0]["target"] == "message"
    assert python_dumped["input"][0]["path"] == "input.message"
    assert python_dumped["output"][0]["source"] == "echoed"
    assert python_dumped["output"][0]["target"] == "state.echoed"
    assert json_dumped["input"][0]["target"] == "message"
    assert json_dumped["input"][0]["path"] == "input.message"
    assert json_dumped["output"][0]["source"] == "echoed"
    assert json_dumped["output"][0]["target"] == "state.echoed"


def test_node_use_rejects_mixed_old_and_new_binding_styles():
    with pytest.raises(ValidationError):
        NodeUse.model_validate({
            "id": "echo",
            "type": "node",
            "node": "echo",
            "input": [{"target": "message", "path": "input.message"}],
            "in_map": {"input.other": "other"},
        })


def test_input_binding_rejects_path_and_value_together():
    with pytest.raises(ValidationError):
        NodeUse.model_validate({
            "id": "bad",
            "type": "node",
            "node": "bad",
            "input": [{"target": "message", "path": "input.message", "value": "x"}],
        })


def test_input_binding_rejects_neither_path_nor_value():
    with pytest.raises(ValidationError):
        NodeUse.model_validate({
            "id": "bad",
            "type": "node",
            "node": "bad",
            "input": [{"target": "message"}],
        })


@pytest.mark.parametrize(
    "field,binding",
    [
        ("input", {"target": "message", "path": "input.message", "extra": True}),
        ("output", {"source": "echoed", "target": "state.echoed", "extra": True}),
    ],
)
def test_bindings_reject_extra_fields(field: str, binding: dict[str, object]):
    with pytest.raises(ValidationError):
        NodeUse.model_validate({
            "id": "bad",
            "type": "node",
            "node": "bad",
            field: [binding],
        })


@pytest.mark.parametrize(
    "field,value",
    [
        ("in_map", None),
        ("input_values", []),
        ("out_map", "bad"),
    ],
)
def test_deprecated_maps_reject_non_mapping_values(field: str, value: object):
    with pytest.raises(ValidationError):
        NodeUse.model_validate({
            "id": "bad",
            "type": "node",
            "node": "bad",
            field: value,
        })


def test_deprecated_conversion_preserves_input_value_then_in_map_order():
    node = NodeUse.model_validate({
        "id": "ordered",
        "type": "node",
        "node": "ordered",
        "input_values": {"first": 1, "second": 2},
        "in_map": {"input.third": "third", "state.fourth": "fourth"},
    })

    dumped_input = node.model_dump(mode="json")["input"]
    assert dumped_input[0]["target"] == "first"
    assert dumped_input[0]["value"] == 1
    assert dumped_input[1]["target"] == "second"
    assert dumped_input[1]["value"] == 2
    assert dumped_input[2]["target"] == "third"
    assert dumped_input[2]["path"] == "input.third"
    assert dumped_input[3]["target"] == "fourth"
    assert dumped_input[3]["path"] == "state.fourth"


def test_deprecated_input_value_preserves_explicit_null():
    node = NodeUse.model_validate({
        "id": "null",
        "type": "node",
        "node": "null",
        "input_values": {"maybe": None},
    })

    value_binding = node.input[0]
    assert isinstance(value_binding, InputValueBinding)
    assert value_binding.value is None

    dumped_input = node.model_dump(mode="json")["input"]
    assert dumped_input[0]["target"] == "maybe"
    assert dumped_input[0]["value"] is None
