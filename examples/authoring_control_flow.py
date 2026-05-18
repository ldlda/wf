from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from wf_authoring import NodeReturn, NodeSpec, WorkflowBuilder, node, outcome, state
from wf_core import END


class TextInput(BaseModel):
    """Common workflow input used by the authoring examples."""

    text: str


class ExampleState(BaseModel):
    """Small shared state shape so examples can focus on control flow."""

    message: str = ""
    status: str = ""
    length: int = 0


class MessageOutput(BaseModel):
    """Common workflow output payload."""

    message: str


class StatusOutput(BaseModel):
    """Intermediate node output that records a status in workflow state."""

    status: str


class MetricsOutput(BaseModel):
    """Intermediate node output used by condition examples."""

    message: str
    length: int


@node(outcomes=("send", "skip", "error"))
def classify_message(input: TextInput) -> NodeReturn[MessageOutput]:
    """Choose an outcome directly from node logic."""
    if input.text == "bad":
        return outcome("error", MessageOutput(message="classification failed"))
    if "send" in input.text:
        return outcome("send", MessageOutput(message=input.text))
    return outcome("skip", MessageOutput(message=input.text))


@node(outcomes=("ok", "error"))
def lookup_message(input: TextInput) -> NodeReturn[MessageOutput]:
    """Pretend to fetch data and expose a business error outcome."""
    if input.text == "bad":
        return outcome("error", MessageOutput(message="lookup failed"))
    return outcome("ok", MessageOutput(message=input.text))


@node(outcomes=("ok", "error"))
def deliver_message(input: MessageOutput) -> NodeReturn[MessageOutput]:
    """Pretend delivery can also fail with the same error outcome."""
    if input.message == "undeliverable":
        return outcome("error", MessageOutput(message="delivery failed"))
    return outcome("ok", MessageOutput(message=f"delivered: {input.message}"))


@node
def mark_sent(input: MessageOutput) -> MessageOutput:
    """Normalize the branch payload for the send path."""
    return MessageOutput(message=f"sent: {input.message}")


@node
def mark_skipped(input: MessageOutput) -> MessageOutput:
    """Normalize the branch payload for the skip path."""
    return MessageOutput(message=f"skipped: {input.message}")


@node
def fail_safely(input: MessageOutput) -> MessageOutput:
    """Collapse several error outcomes into one workflow-facing payload."""
    return MessageOutput(message="failed safely")


@node
def classify_status(input: TextInput) -> StatusOutput:
    """Write a status value for `match()` to inspect."""
    if input.text == "approve":
        return StatusOutput(status="approved")
    if input.text == "reject":
        return StatusOutput(status="rejected")
    return StatusOutput(status="pending")


@node
def approved(input: StatusOutput) -> MessageOutput:
    """Target for the approved status."""
    return MessageOutput(message="approved")


@node
def rejected(input: StatusOutput) -> MessageOutput:
    """Target for the rejected status."""
    return MessageOutput(message="rejected")


@node
def pending(input: StatusOutput) -> MessageOutput:
    """Target for the pending/default status."""
    return MessageOutput(message="pending")


@node
def measure_text(input: TextInput) -> MetricsOutput:
    """Record derived state for `when()` and `choose()` examples."""
    return MetricsOutput(message=input.text, length=len(input.text))


@node
def enthusiastic(input: MetricsOutput) -> MessageOutput:
    """Target used when text is long enough to be considered excited."""
    return MessageOutput(message="enthusiastic")


@node
def calm(input: MetricsOutput) -> MessageOutput:
    """Target used when text is not long enough for the positive branch."""
    return MessageOutput(message="calm")


@node
def long_message(input: MetricsOutput) -> MessageOutput:
    """Target for the first true `choose()` clause."""
    return MessageOutput(message="long")


@node
def medium_message(input: MetricsOutput) -> MessageOutput:
    """Target for a later `choose()` clause."""
    return MessageOutput(message="medium")


@node
def short_message(input: MetricsOutput) -> MessageOutput:
    """Default target for the ordered predicate chain."""
    return MessageOutput(message="short")


def _graph(name: str) -> WorkflowBuilder:
    """Create the shared example graph shell."""
    return WorkflowBuilder(
        name=name,
        input_schema=TextInput,
        state_schema=ExampleState,
        output_schema=MessageOutput,
    )


def _message_use(
    graph: WorkflowBuilder,
    spec: NodeSpec[Any, MessageOutput],
    *,
    id: str,
):
    """Use a message node with explicit state mappings for readability."""
    return graph.use(
        spec,
        id=id,
        in_map={"state.message": "message"},
        out_map={"message": "state.message"},
    )


def _status_use(
    graph: WorkflowBuilder,
    spec: NodeSpec[Any, MessageOutput],
    *,
    id: str,
):
    """Use a status target with explicit state mappings for readability."""
    return graph.use(
        spec,
        id=id,
        in_map={"state.status": "status"},
        out_map={"message": "state.message"},
    )


def _metrics_use(
    graph: WorkflowBuilder,
    spec: NodeSpec[Any, MessageOutput],
    *,
    id: str,
):
    """Use a metrics target with explicit state mappings for readability."""
    return graph.use(
        spec,
        id=id,
        in_map={
            "state.message": "message",
            "state.length": "length",
        },
        out_map={"message": "state.message"},
    )


def build_branch_workflow() -> WorkflowBuilder:
    """Build a workflow that demonstrates outcome routing with `branch()`."""
    graph = _graph("branch_example")
    router = graph.use(
        classify_message,
        id="classify",
        in_map={"input.text": "text"},
        out_map={"message": "state.message"},
    )
    graph.branch(
        router,
        {
            "send": _message_use(graph, mark_sent, id="sent"),
            "skip": _message_use(graph, mark_skipped, id="skipped"),
            "error": _message_use(graph, fail_safely, id="failed"),
        },
    )
    graph.connect("sent", "ok", END)
    graph.connect("skipped", "ok", END)
    graph.connect("failed", "ok", END)
    graph.set_entry_point(router)
    return graph


def build_handle_workflow() -> WorkflowBuilder:
    """Build a workflow that demonstrates shared error handling."""
    graph = _graph("handle_example")
    lookup = graph.use(
        lookup_message,
        id="lookup",
        in_map={"input.text": "text"},
        out_map={"message": "state.message"},
    )
    deliver = _message_use(graph, deliver_message, id="deliver")
    failed = _message_use(graph, fail_safely, id="failed")
    graph.connect(lookup, "ok", deliver)
    graph.connect(deliver, "ok", END)
    graph.handle((lookup, "error"), (deliver, "error"), to=failed)
    graph.connect(failed, "ok", END)
    graph.set_entry_point(lookup)
    return graph


def build_match_workflow() -> WorkflowBuilder:
    """Build a workflow that demonstrates equality dispatch with `match()`."""
    graph = _graph("match_example")
    classifier = graph.use(
        classify_status,
        id="classify_status",
        in_map={"input.text": "text"},
        out_map={"status": "state.status"},
    )
    decision = graph.match(
        state("status"),
        {
            "approved": _status_use(graph, approved, id="approved"),
            "rejected": _status_use(graph, rejected, id="rejected"),
        },
        default=_status_use(graph, pending, id="pending"),
        id="status",
    )
    graph.connect(classifier, "ok", decision.entry)
    graph.connect("approved", "ok", END)
    graph.connect("rejected", "ok", END)
    graph.connect("pending", "ok", END)
    graph.set_entry_point(classifier)
    return graph


def build_when_workflow() -> WorkflowBuilder:
    """Build a workflow that demonstrates one boolean condition with `when()`."""
    graph = _graph("when_example")
    measure = graph.use(
        measure_text,
        id="measure",
        in_map={"input.text": "text"},
        out_map={
            "message": "state.message",
            "length": "state.length",
        },
    )
    decision = graph.when(
        state("length").ge(6),
        then=_metrics_use(graph, enthusiastic, id="enthusiastic"),
        otherwise=_metrics_use(graph, calm, id="calm"),
        id="long_enough",
    )
    graph.connect(measure, "ok", decision.entry)
    graph.connect("enthusiastic", "ok", END)
    graph.connect("calm", "ok", END)
    graph.set_entry_point(measure)
    return graph


def build_choose_workflow() -> WorkflowBuilder:
    """Build a workflow that demonstrates ordered predicates with `choose()`."""
    graph = _graph("choose_example")
    measure = graph.use(
        measure_text,
        id="measure",
        in_map={"input.text": "text"},
        out_map={
            "message": "state.message",
            "length": "state.length",
        },
    )
    decision = graph.choose(
        (state("length").ge(20), _metrics_use(graph, long_message, id="long")),
        (state("length").ge(8), _metrics_use(graph, medium_message, id="medium")),
        default=_metrics_use(graph, short_message, id="short"),
        id="message_size",
    )
    graph.connect(measure, "ok", decision.entry)
    graph.connect("long", "ok", END)
    graph.connect("medium", "ok", END)
    graph.connect("short", "ok", END)
    graph.set_entry_point(measure)
    return graph


def build_use_ref_workflow() -> WorkflowBuilder:
    """Compile a graph that references an externally resolved capability."""
    graph = _graph("use_ref_example")
    echo = graph.use_ref(
        "demo.echo",
        id="echo",
        in_map={"input.text": "message"},
        out_map={"echoed": "state.message"},
    )
    graph.connect(echo, "ok", END)
    graph.set_entry_point(echo)
    return graph


def main() -> None:
    """Run a few examples directly from the command line."""
    for build, payload in (
        (build_branch_workflow, {"text": "send this"}),
        (build_match_workflow, {"text": "approve"}),
        (build_choose_workflow, {"text": "this is a very long message"}),
    ):
        graph = build()
        run = graph.execute(payload)
        print(graph.name, run.status.value, run.output)


if __name__ == "__main__":
    main()
