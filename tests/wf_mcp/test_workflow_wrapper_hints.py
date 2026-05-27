from __future__ import annotations

from wf_mcp.workflow_surface.wrapper_hints import (
    MissingDecision,
    MissingDecisionKind,
    OutcomeCandidate,
    OutcomeCandidateKind,
    WrapperAuthoringHints,
    WrapperHintConfidence,
    WrapperOutcomePolicy,
    wrapper_hints_for_capability,
)


def test_wrapper_hint_models_serialize_enum_fields_as_strings() -> None:
    hints = WrapperAuthoringHints(
        capability_name="demo.personal.echo_tool",
        confidence=WrapperHintConfidence.MEDIUM,
        declared_outcomes=["ok", "error"],
        suggested_wrapper_outcomes=["ok", "error"],
        outcome_policy=WrapperOutcomePolicy.PRESERVE_DECLARED,
        input_schema={"type": "object", "properties": {}},
        state_schema={"type": "object", "properties": {}},
        output_schema={"type": "object", "properties": {}},
        input_map={},
        output_map={},
        outcome_candidates=[
            OutcomeCandidate(
                kind=OutcomeCandidateKind.BOOLEAN_CONTROL_FIELD,
                source="output.success",
                candidate_outcomes=["success", "failure"],
                confidence=WrapperHintConfidence.MEDIUM,
                reason="top-level boolean field with control-like name",
                automatic=False,
            )
        ],
        missing_decisions=[
            MissingDecision(
                kind=MissingDecisionKind.CONFIRM_BOOLEAN_OUTCOMES,
                message="Confirm whether output.success should control routing.",
            )
        ],
        notes=["Hints are scaffolding, not semantic guarantees."],
    )

    dumped = hints.model_dump(mode="json")

    assert dumped["confidence"] == "medium"
    assert dumped["outcome_policy"] == "preserve_declared"
    assert dumped["outcome_candidates"][0]["kind"] == "boolean_control_field"
    assert dumped["missing_decisions"][0]["kind"] == "confirm_boolean_outcomes"


def test_wrapper_hints_scaffold_simple_object_input_and_output() -> None:
    hints = wrapper_hints_for_capability(
        capability_name="demo.personal.echo_tool",
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        output_schema={
            "type": "object",
            "properties": {"echoed": {"type": "string"}},
            "required": ["echoed"],
        },
        outcomes=["ok"],
    )

    dumped = hints.model_dump(mode="json")

    assert dumped["confidence"] == "high"
    assert dumped["declared_outcomes"] == ["ok"]
    assert dumped["suggested_wrapper_outcomes"] == ["ok"]
    assert dumped["outcome_policy"] == "preserve_declared"
    assert dumped["input_map"] == {"input.text": "text"}
    assert dumped["output_map"] == {"echoed": "state.echoed"}
    assert dumped["state_schema"]["properties"]["echoed"]["type"] == "string"
    assert dumped["output_schema"]["properties"]["echoed"]["type"] == "string"
    assert dumped["missing_decisions"] == []


def test_wrapper_hints_offer_boolean_outcome_candidates_without_auto_mapping() -> None:
    hints = wrapper_hints_for_capability(
        capability_name="demo.personal.submit",
        input_schema={"type": "object", "properties": {"text": {"type": "string"}}},
        output_schema={
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "message": {"type": "string"},
            },
        },
        outcomes=["ok"],
    )

    dumped = hints.model_dump(mode="json")
    candidate = dumped["outcome_candidates"][0]

    assert dumped["confidence"] == "medium"
    assert candidate["kind"] == "boolean_control_field"
    assert candidate["source"] == "output.success"
    assert candidate["candidate_outcomes"] == ["success", "failure"]
    assert candidate["automatic"] is False
    assert dumped["outcome_policy"] == "preserve_declared"
    assert dumped["suggested_wrapper_outcomes"] == ["ok"]
    assert dumped["missing_decisions"][0]["kind"] == "confirm_boolean_outcomes"


def test_wrapper_hints_do_not_treat_arbitrary_booleans_as_outcomes() -> None:
    hints = wrapper_hints_for_capability(
        capability_name="demo.personal.profile",
        input_schema={"type": "object", "properties": {"user_id": {"type": "string"}}},
        output_schema={
            "type": "object",
            "properties": {
                "is_admin": {"type": "boolean"},
                "name": {"type": "string"},
            },
        },
        outcomes=["ok"],
    )

    dumped = hints.model_dump(mode="json")

    assert dumped["confidence"] == "high"
    assert dumped["outcome_candidates"] == []
    assert dumped["missing_decisions"] == []


def test_wrapper_hints_mark_nested_outputs_as_low_confidence() -> None:
    hints = wrapper_hints_for_capability(
        capability_name="demo.personal.search",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        output_schema={
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"title": {"type": "string"}},
                    },
                }
            },
        },
        outcomes=["ok"],
    )

    dumped = hints.model_dump(mode="json")

    assert dumped["confidence"] == "low"
    assert dumped["missing_decisions"][0]["kind"] == "review_nested_output"
    assert dumped["output_map"] == {"results": "state.results"}


def test_wrapper_hints_do_not_auto_map_raw_mcp_content_blocks() -> None:
    hints = wrapper_hints_for_capability(
        capability_name="everything.default.echo",
        input_schema={
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "content": {"type": "array"},
            },
        },
        outcomes=["ok", "error"],
    )

    dumped = hints.model_dump(mode="json")

    assert dumped["confidence"] == "low"
    assert dumped["output_map"] == {}
    assert "content" not in dumped["state_schema"]["properties"]
    assert dumped["missing_decisions"][0]["kind"] == "review_nested_output"
    assert "Raw MCP content blocks" in dumped["notes"][2]


def test_wrapper_hints_keep_content_only_mcp_output_explicit() -> None:
    hints = wrapper_hints_for_capability(
        capability_name="everything.default.echo",
        input_schema={
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
        output_schema={
            "type": "object",
            "properties": {"content": {"type": "array"}},
            "required": ["content"],
        },
        outcomes=["ok", "error"],
    )

    dumped = hints.model_dump(mode="json")

    assert dumped["confidence"] == "low"
    assert dumped["output_map"] == {}
    assert "content" not in dumped["state_schema"]["properties"]
    assert dumped["output_schema"]["properties"] == {}
    assert dumped["missing_decisions"][0]["kind"] == "review_nested_output"
    assert "TextContent" in dumped["notes"][2]


def test_wrapper_hints_mark_empty_output_schema_as_low_confidence() -> None:
    hints = wrapper_hints_for_capability(
        capability_name="demo.personal.no_output",
        input_schema={"type": "object", "properties": {"text": {"type": "string"}}},
        output_schema={"type": "object", "properties": {}},
        outcomes=["ok"],
    )

    dumped = hints.model_dump(mode="json")

    assert dumped["confidence"] == "low"
    assert dumped["input_map"] == {"input.text": "text"}
    assert dumped["output_map"] == {}
    assert dumped["missing_decisions"][0]["kind"] == "choose_output_fields"
