from __future__ import annotations

import pytest

from wf_core import (
    END,
    Edge,
    NodeDef,
    NodeUse,
    ReducerRef,
    ReducerSpec,
    SchemaRef,
    SiblingWritePolicy,
    StateField,
    StateSchema,
    Workflow,
    WorkflowExecutionError,
)
from wf_core.paths import StatePath
from wf_core.run_state import StateWrite
from wf_core.models.steps import OutputBinding
from wf_core.runtime.engine import resume_workflow
from wf_core.runtime.ops.merges import ReducerDefinition
from wf_core.runtime.ops.runs import create_run_state
from wf_core.runtime.ops.state import (
    StatePatch,
    apply_output_bindings,
    build_barrier_patch,
    build_output_patch,
    commit_state_patch,
)


def test_output_bindings_commit_patch_atomically_when_source_is_missing() -> None:
    workflow = _workflow()
    state = {"person": {"name": "old"}}

    with pytest.raises(WorkflowExecutionError, match="missing"):
        apply_output_bindings(
            workflow,
            [
                _binding("person.name", "state.person.name"),
                _binding("missing", "state.person.extra"),
            ],
            {"person": {"name": "new"}},
            state,
        )

    assert state["person"]["name"] == "old"
    assert "extra" not in state["person"]


def test_output_bindings_reject_overlapping_write_targets_before_mutation() -> None:
    workflow = _workflow()
    state = {"person": {"name": "old"}}

    with pytest.raises(WorkflowExecutionError, match="overlapping"):
        apply_output_bindings(
            workflow,
            [
                _binding("person", "state.person"),
                _binding("person.name", "state.person.name"),
            ],
            {"person": {"name": "Ada"}},
            state,
        )

    assert state["person"]["name"] == "old"


def test_output_bindings_prepare_reducer_results_before_mutation() -> None:
    workflow = _workflow(
        fields={
            "person.name": StateField(type="string"),
            "person.tags": StateField(
                type="array",
                reducer=ReducerRef(name="wf.std.set_union", config={"bad": True}),
            ),
        }
    )
    state = {"person": {"name": "old", "tags": ["seed"]}}

    with pytest.raises(WorkflowExecutionError, match="reducer config"):
        apply_output_bindings(
            workflow,
            [
                _binding("person.name", "state.person.name"),
                _binding("person.tags", "state.person.tags"),
            ],
            {"person": {"name": "new", "tags": ["next"]}},
            state,
        )

    assert state["person"]["name"] == "old"
    assert state["person"]["tags"][0] == "seed"
    assert len(state["person"]["tags"]) == 1


def test_output_bindings_commit_to_staged_state_before_mutating_original() -> None:
    workflow = _workflow(
        fields={
            "person.name": StateField(type="string"),
            "blocked.child": StateField(type="string"),
        }
    )
    state = {"person": {"name": "old"}, "blocked": "not-an-object"}

    with pytest.raises(WorkflowExecutionError, match="cannot descend"):
        apply_output_bindings(
            workflow,
            [
                _binding("person.name", "state.person.name"),
                _binding("blocked.child", "state.blocked.child"),
            ],
            {"person": {"name": "new"}, "blocked": {"child": "value"}},
            state,
        )

    assert state["person"]["name"] == "old"
    assert state["blocked"] == "not-an-object"


def test_output_bindings_validate_exact_state_schema_before_mutation() -> None:
    workflow = _workflow(fields={"person.name": StateField(type="string")})
    state = {"person": {"name": "old"}}

    with pytest.raises(WorkflowExecutionError, match="state write state.person.name"):
        apply_output_bindings(
            workflow,
            [_binding("person.name", "state.person.name")],
            {"person": {"name": 7}},
            state,
        )

    assert state["person"]["name"] == "old"


def test_output_bindings_validate_declared_parent_schema_before_mutation() -> None:
    workflow = _workflow_from_state_schema(
        StateSchema.model_validate(
            {
                "type": "object",
                "properties": {
                    "person": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "additionalProperties": False,
                    }
                },
            }
        )
    )
    state = {"person": {"name": "old"}}

    with pytest.raises(WorkflowExecutionError, match="state write state.person"):
        apply_output_bindings(
            workflow,
            [_binding("person.extra", "state.person.extra")],
            {"person": {"extra": "bad"}},
            state,
        )

    assert state["person"] == {"name": "old"}


def test_full_workflow_execution_writes_canonical_output_bindings() -> None:
    workflow = _workflow_with_node()
    run = create_run_state(workflow, {})

    run = resume_workflow(
        workflow,
        run,
        {
            "rename": lambda _payload, _ctx: {
                "outcome": "ok",
                "output": {"person": {"name": "Ada"}},
            }
        },
    )

    assert run.state["person"]["name"] == "Ada"
    assert run.trace[0].state_changes["state.person.name"] == "Ada"


def test_build_output_patch_does_not_mutate_until_commit() -> None:
    workflow = _workflow(fields={"person.name": StateField(type="string")})
    state = {"person": {"name": "old"}}

    patch = build_output_patch(
        workflow,
        [_binding("person.name", "state.person.name")],
        {"person": {"name": "Ada"}},
        state,
    )

    assert state["person"]["name"] == "old"
    assert patch.changes["state.person.name"] == "Ada"

    committed = commit_state_patch(state, patch)

    assert committed["state.person.name"] == "Ada"
    assert state["person"]["name"] == "Ada"


def test_output_patch_records_incoming_and_visible_values() -> None:
    workflow = _workflow(
        fields={
            "count": StateField(
                type="integer",
                reducer=ReducerRef(name="wf.std.add"),
            )
        }
    )
    state = {"count": 2}

    patch = build_output_patch(
        workflow,
        [_binding("delta", "state.count")],
        {"delta": 3},
        state,
    )

    assert patch.changes["state.count"] == 3
    assert patch.visible_values["state.count"] == 5
    assert patch.writes[0].incoming_value == 3
    assert patch.writes[0].visible_value == 5


def test_barrier_replays_incoming_values_not_lineage_visible_values() -> None:
    workflow = _workflow(
        fields={
            "number": StateField(
                type="integer",
                reducer=ReducerRef(name="wf.std.add"),
            )
        }
    )
    patch = build_barrier_patch(
        workflow,
        [
            StatePatch(
                writes=[
                    StateWrite(
                        path=StatePath(("number",)),
                        incoming_value=3,
                        visible_value=5,
                        reducer=ReducerRef(name="wf.std.add"),
                    )
                ]
            ),
            StatePatch(
                writes=[
                    StateWrite(
                        path=StatePath(("number",)),
                        incoming_value=1,
                        visible_value=3,
                        reducer=ReducerRef(name="wf.std.add"),
                    )
                ]
            ),
        ],
        {"number": 2},
    )

    assert patch.changes["state.number"] == 6
    assert patch.visible_values["state.number"] == 6


def test_build_and_commit_patch_matches_apply_output_bindings() -> None:
    workflow = _workflow(fields={"person.name": StateField(type="string")})
    state_from_apply = {"person": {"name": "old"}}
    state_from_patch = {"person": {"name": "old"}}
    bindings = [_binding("person.name", "state.person.name")]
    output = {"person": {"name": "Ada"}}

    applied = apply_output_bindings(workflow, bindings, output, state_from_apply)
    patch = build_output_patch(workflow, bindings, output, state_from_patch)
    committed = commit_state_patch(state_from_patch, patch)

    assert applied["state.person.name"] == committed["state.person.name"]
    assert state_from_apply["person"]["name"] == state_from_patch["person"]["name"]


def test_state_patch_rejects_inconsistent_trace_changes_and_writes() -> None:
    with pytest.raises(ValueError, match="inconsistent changes and writes"):
        StatePatch(
            changes={"state.value": "trace"},
            writes=[
                StateWrite(
                    path=StatePath(("value",)),
                    incoming_value="actual",
                    visible_value="actual",
                    reducer=ReducerRef(name="wf.std.replace"),
                )
            ],
        )


def test_barrier_rejects_sibling_same_path_writes_without_reducer() -> None:
    workflow = _workflow(fields={"value": StateField(type="string")})

    with pytest.raises(WorkflowExecutionError, match="mergeable reducer"):
        build_barrier_patch(
            workflow,
            [
                StatePatch(changes={"state.value": "a"}),
                StatePatch(changes={"state.value": "b"}),
            ],
            {},
        )


def test_barrier_rejects_sibling_same_path_writes_with_explicit_replace() -> None:
    workflow = _workflow(
        fields={
            "value": StateField(
                type="string",
                reducer=ReducerRef(name="wf.std.replace"),
            )
        }
    )

    with pytest.raises(WorkflowExecutionError, match="mergeable reducer"):
        build_barrier_patch(
            workflow,
            [
                StatePatch(changes={"state.value": "a"}),
                StatePatch(changes={"state.value": "b"}),
            ],
            {},
        )


def test_barrier_allows_sibling_same_path_writes_with_non_replace_reducer() -> None:
    workflow = _workflow(
        fields={
            "seen": StateField(
                type="array",
                reducer=ReducerRef(name="wf.std.append"),
            )
        }
    )

    patch = build_barrier_patch(
        workflow,
        [
            StatePatch(changes={"state.seen": "a"}),
            StatePatch(changes={"state.seen": "b"}),
        ],
        {},
    )

    assert patch.changes["state.seen"] == ["a", "b"]


def test_barrier_uses_reducer_policy_instead_of_reducer_name() -> None:
    workflow = _workflow(
        fields={
            "value": StateField(
                type="integer",
                reducer=ReducerRef(name="test.keep_latest"),
            )
        }
    )
    reducer = ReducerDefinition(
        spec=ReducerSpec(name="test.keep_latest"),
        fn=lambda _current, incoming: incoming,
    )

    patch = build_barrier_patch(
        workflow,
        [
            StatePatch(changes={"state.value": 1}),
            StatePatch(changes={"state.value": 2}),
        ],
        {},
        reducers={"test.keep_latest": reducer},
    )

    assert patch.changes["state.value"] == 2


def test_barrier_rejects_custom_exclusive_reducer() -> None:
    workflow = _workflow(
        fields={
            "value": StateField(
                type="integer",
                reducer=ReducerRef(name="test.last"),
            )
        }
    )
    reducer = ReducerDefinition(
        spec=ReducerSpec(
            name="test.last",
            sibling_write_policy=SiblingWritePolicy.EXCLUSIVE,
        ),
        fn=lambda _current, incoming: incoming,
    )

    with pytest.raises(WorkflowExecutionError, match="mergeable reducer"):
        build_barrier_patch(
            workflow,
            [
                StatePatch(changes={"state.value": 1}),
                StatePatch(changes={"state.value": 2}),
            ],
            {},
            reducers={"test.last": reducer},
        )


def test_barrier_rejects_sibling_ancestor_descendant_writes() -> None:
    workflow = _workflow_from_state_schema(
        StateSchema.model_validate(
            {
                "type": "object",
                "properties": {
                    "person": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                    }
                },
            }
        )
    )

    with pytest.raises(WorkflowExecutionError, match="overlapping sibling writes"):
        build_barrier_patch(
            workflow,
            [
                StatePatch(changes={"state.person": {"name": "Ada"}}),
                StatePatch(changes={"state.person.name": "Grace"}),
            ],
            {},
        )


def _binding(source: str, target: str) -> OutputBinding:
    return OutputBinding.model_validate({"source": source, "target": target})


def _workflow(
    fields: dict[str, StateField] | None = None,
) -> Workflow:
    return _workflow_from_state_schema(
        StateSchema.from_field_map(
            fields
            or {
                "person": StateField(type="object"),
                "person.name": StateField(type="string"),
                "person.extra": StateField(type="string"),
            }
        )
    )


def _workflow_from_state_schema(state_schema: StateSchema) -> Workflow:
    return Workflow(
        name="patch",
        input_schema=SchemaRef(type="object", properties={}),
        state_schema=state_schema,
        output_schema=SchemaRef(type="object", properties={}),
        start="n",
        nodes=[],
        edges=[],
    )


def _workflow_with_node() -> Workflow:
    return Workflow(
        name="canonical_output",
        input_schema=SchemaRef(type="object", properties={}),
        state_schema=StateSchema.from_field_map(
            {"person.name": StateField(type="string")}
        ),
        output_schema=SchemaRef(
            type="object", properties={"person": {"type": "object"}}
        ),
        node_defs=[
            NodeDef(
                name="rename",
                input_schema=SchemaRef(type="object", properties={}),
                output_schema=SchemaRef(
                    type="object",
                    properties={"person": {"type": "object"}},
                ),
                outcomes=["ok"],
            )
        ],
        start="rename",
        nodes=[
            NodeUse.model_validate(
                {
                    "id": "rename",
                    "type": "node",
                    "node": "rename",
                    "output": [
                        {"source": "person.name", "target": "state.person.name"}
                    ],
                }
            )
        ],
        edges=[Edge.model_validate({"from": "rename", "outcome": "ok", "to": END})],
    )
