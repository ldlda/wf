# Python Workflow Lifecycle

This reference contains complete patterns for the public `wf_client` API.

## Typed Authoring With Contract Replacement

```python
from pydantic import BaseModel

from wf_authoring import input_from, input_value, output_to, state_path
from wf_client import App


class InitialInput(BaseModel):
    request_id: str


class InitialState(BaseModel):
    value: str | None = None


class InitialOutput(BaseModel):
    value: str


class ExpandedState(BaseModel):
    value: str | None = None
    source: str | None = None


class FinalOutput(BaseModel):
    value: str


app = App.from_http_jsonrpc("http://localhost:8765/rpc")
constant = await app.capability("wf.std.constant")

graph = app.new_workflow(
    "typed_example",
    input_schema=InitialInput,
    state_schema=InitialState,
    output_schema=InitialOutput,
)
step = graph.use(
    constant,
    id="constant",
    input=[input_value("value", "hello")],
    output=[output_to("value", state_path("value"))],
)

graph.set_contract(state_schema=ExpandedState, output_schema=FinalOutput)

end = graph.end("ok", id="end_ok")
graph.set_entry_point(step)
graph.connect(step, "ok", end)
graph.set_output([input_from(state_path("value"), "value")])

graph.validate_local().raise_for_errors()
validation = await graph.validate()
validation.raise_for_errors()
artifact = await graph.save(version=1, title="Typed example")
run = await artifact.run({"request_id": "request-1"})
```

## Saved Workflow As A Native Subgraph

Load the exact child artifact before authoring the parent. Its public contract
is copied into the parent boundary for local validation; its artifact ID and
version remain the runtime dependency.

```python
from wf_authoring import input_from, input_path, output_to, state_path

child = await app.workflow("child", version=2)
parent = app.new_workflow(
    "parent",
    input_schema=ParentInput,
    state_schema=ParentState,
    output_schema=ParentOutput,
)
run_child = parent.subgraph(
    child,
    id="run_child",
    input=[input_from(input_path("prompt"), "prompt")],
    output=[output_to("value", state_path("result"))],
)
parent.set_entry_point(run_child)
parent.connect(run_child, "ok", parent.end("ok", id="parent_done"))
parent.set_output([input_from(state_path("result"), "result")])

parent.validate_local().raise_for_errors()
(await parent.validate()).raise_for_errors()
parent_v1 = await parent.save(version=1)

deployment = await parent_v1.deploy("parent.production")
readiness = await deployment.validate()
if not readiness.runnable:
    raise RuntimeError(readiness.diagnostics)
run = await deployment.run({"prompt": "hello"})
```

Choose binding paths from `child.inspect()` and the parent models. Saving the
parent does not duplicate the child plan: the saved parent retains the exact
`child.v2` dependency, which deployment validation and execution resolve.

## Lossless Editing

```python
artifact = await app.workflow("report", version=3)
workflow = artifact.inspect()
print([node.id for node in workflow.nodes])

summarize = await app.capability("app.default.summarize")
graph = artifact.edit()

summary = graph.use(
    summarize,
    id="summarize",
    input=[input_from(state_path("draft"), "text")],
    output=[output_to("summary", state_path("summary"))],
)
graph.set_route("draft_report", "ok", summary)
graph.connect(summary, "ok", "end_ok")

graph.validate_local().raise_for_errors()
(await graph.validate()).raise_for_errors()
report_v4 = await graph.save(version=4)
```

The step IDs and paths above are examples. Inspect the loaded artifact and use
its real contract; do not assume those names exist.

## Deployment Diagnosis And Durable Runs

```python
from wf_client import DeploymentRequired, ProtocolError, WorkflowClientError

artifact = await app.workflow("invoice", version=2)

try:
    run = await artifact.run({"invoice_id": "INV-1001"})
except DeploymentRequired as error:
    print("candidates", error.candidate_deployment_ids)
    print("unresolved", error.unresolved_logical_sources)
    for diagnostic in error.diagnostics:
        print(diagnostic.code, diagnostic.message)
except ProtocolError as error:
    print("server error", error.code, error.message, error.data)
    raise
except WorkflowClientError as error:
    print(type(error).__name__, error)
    raise

deployment = await artifact.deploy(
    "invoice.production",
    bindings={"billing": "production.billing"},
)
readiness = await deployment.validate()
if not readiness.runnable:
    for diagnostic in readiness.diagnostics:
        print(diagnostic.code, diagnostic.message)
    raise RuntimeError("invoice.production is not runnable")

run = await deployment.run({"invoice_id": "INV-1001"})

if run.status == "interrupted" and run.interrupt is not None:
    run = await run.resume({"approved": True})

run = await run.refresh()
trace = await run.trace(start=0, limit=25)
for frame in trace.frames:
    print(frame)
```

Catch the specific public errors useful to the application and retain a final
`WorkflowClientError` fallback. Unknown server errors remain inspectable
`ProtocolError` values with `code`, `message`, and `data`.
