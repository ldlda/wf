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
from wf_client import DeploymentRequired, WorkflowClientError

artifact = await app.workflow("invoice", version=2)

try:
    run = await artifact.run({"invoice_id": "INV-1001"})
except DeploymentRequired as error:
    print("candidates", error.candidate_deployment_ids)
    print("unresolved", error.unresolved_logical_sources)
    for diagnostic in error.diagnostics:
        print(diagnostic.code, diagnostic.message)

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
