---
name: wf-python
description: Use when writing, reviewing, or debugging Python code that uses wf_client App, RemoteCapability, EditableWorkflow, WorkflowArtifact, Deployment, Run, or the Python workflow lifecycle. Prefer this skill for Python workflow authoring, typed contracts, artifact editing, deployment selection, interrupts, and traces; use wf-cli instead for shell-first work.
---

# wf Python Client

Use `wf_client` as the public Python object API over the workflow service. Keep
JSON-RPC payloads, codecs, stores, and draft workspaces below this boundary.

## Start With The Right Object

```python
from wf_client import App

app = App.from_http_jsonrpc("http://localhost:8765/rpc")
capability = await app.capability("app.default.thing")
```

Choose the object that matches the operation:

- `RemoteCapability`: inspect or directly probe one capability.
- `EditableWorkflow`: author or revise a graph locally.
- `WorkflowArtifact`: inspect one immutable saved version.
- `Deployment`: bind one artifact version to concrete sources and validate it.
- `Run`: inspect, refresh, resume, or trace one durable execution.

Discover existing saved objects as lightweight summaries, then load the exact
object selected by the application:

```python
artifacts = await app.artifacts(query="report", kind="workflow")
deployments = await app.deployments()
runs = await app.runs(status="interrupted", limit=25)

artifact = await app.workflow(
    artifacts.items[0].artifact_id,
    version=artifacts.items[0].version,
)
run = await app.run(runs.items[0].run_id)
```

Artifact and run discovery are paged. Deployment discovery returns an immutable
tuple because the server operation is not paged. Listing never reconstructs
full objects or loads run traces.

Do not collapse artifact saving, deployment configuration, and execution into
one invented "publish" operation.

## Prefer Python Contract Types

Declare workflow contracts with Pydantic models or supported Python types. The
builder converts them to canonical schemas.

```python
from pydantic import BaseModel

class Input(BaseModel):
    topic: str

class State(BaseModel):
    result: str | None = None

class Output(BaseModel):
    result: str

graph = app.new_workflow(
    "report",
    input_schema=Input,
    state_schema=State,
    output_schema=Output,
)
```

Use raw schema dictionaries only when the caller already owns a JSON Schema or
needs a construct the Python type system cannot express.

### Replace A Contract During Authoring

Use `set_contract()` instead of assigning normalized builder fields directly:

```python
graph.set_contract(
    state_schema=ExpandedState,
    output_schema=FinalOutput,
    outcomes=("completed", "rejected"),
)
```

Supplied fields replace the whole corresponding contract. Omitted fields remain
unchanged. Replacement is atomic: normalization completes before the builder is
mutated. Existing bindings remain, so run local validation after replacement to
find paths invalidated by the new contract.

## Know What The Builder Infers

`graph.use(remote_capability)` registers the capability's node contract. When
bindings are omitted, it can auto-bind matching capability fields against the
workflow's already-declared input and state fields.

It does not invent the workflow's public contract or topology. Keep these
explicit:

- Input, state, and output contract declarations.
- Workflow outcomes when they differ from the default `("ok",)`.
- Entry point.
- Routes and terminal nodes.
- Final workflow-output projection.
- Deployment bindings and selection when the environment is ambiguous.

Prefer canonical `input=[...]` and `output=[...]` binding lists when the
dataflow matters. Auto-binding is useful for exact field-name matches, not a
substitute for deciding semantics.

## Author, Validate, Save

```python
from wf_authoring import input_from, input_value, output_to, state_path

step = graph.use(
    capability,
    id="constant",
    input=[input_value("value", "hello")],
    output=[output_to("value", state_path("result"))],
)
end = graph.end("ok", id="end_ok")
graph.set_entry_point(step)
graph.connect(step, "ok", end)
graph.set_output([input_from(state_path("result"), "result")])

local = graph.validate_local()
local.raise_for_errors()

validation = await graph.validate()
validation.raise_for_errors()

artifact = await graph.save(version=1, title="Report")
```

`validate_local()` performs no remote I/O. `validate()` adds server plan and
dependency validation. `save()` validates, saves, then inspects the exact saved
version before returning its immutable snapshot.

## Edit An Existing Artifact

```python
artifact = await app.workflow("report", version=3)
graph = artifact.edit()
# Equivalent: graph = await app.edit_workflow("report", version=3)
```

Use ordinary builder methods on `graph`. Do not reconstruct an existing graph
from scratch: the seeded editor preserves schemas, bindings, routes, outcomes,
subgraphs, and retained dependency contracts. Save edits as a new immutable
version unless the caller explicitly requests otherwise.

Never guess step IDs or state paths. Inspect `artifact.inspect()` or the
editable graph before choosing mutation targets.

## Deploy And Run

```python
deployment = await artifact.deploy(
    "report.production",
    bindings={"logical.documents": "production.documents"},
)
readiness = await deployment.validate()
if not readiness.runnable:
    for diagnostic in readiness.diagnostics:
        print(diagnostic.code, diagnostic.message)
    raise RuntimeError("deployment is not runnable")

run = await deployment.run({"topic": "workflow systems"})
```

`artifact.run(input)` is convenient only when deployment selection is
unambiguous. Handle `DeploymentRequired` rather than guessing an account or
source binding.

Run snapshots are immutable:

```python
run = await run.refresh()
if run.status == "interrupted" and run.interrupt is not None:
    run = await run.resume({"approved": True})

trace = await run.trace(start=0, limit=25)
for frame in trace.frames:
    print(frame)
```

Trace reads must stay bounded (`limit` is 1 through 100).

## Handle Public Errors

Catch `WorkflowClientError` or its public subclasses. Do not import transport
exceptions or decode wire payloads yourself.

```python
from wf_client import (
    DeploymentRequired,
    ProtocolError,
    TransportError,
    WorkflowClientError,
)

try:
    run = await artifact.run(payload)
except DeploymentRequired as error:
    print(error.candidate_deployment_ids, error.unresolved_logical_sources)
except TransportError as error:
    print("workflow service unavailable", error)
except ProtocolError as error:
    print(error.code, error.message, error.data)
except WorkflowClientError as error:
    print(type(error).__name__, error)
```

## Boundaries

- `wf_client` intentionally has no draft workspace API. Use server/admin or
  console surfaces only when the task is genuinely about drafts.
- Rich representations are inert debugging aids, not a secrecy boundary.
  Schema-level sensitivity metadata is the appropriate future source of truth;
  do not rely on repr redaction to protect credentials.
- Use the public objects before inspecting `wf_api`, RPC clients, codecs, or
  stores. Drop below the client boundary only when implementing the client.

## Structured foreach context

Prefer declared input bindings via the foreach reference:

```python
orders = graph.foreach(
    id="orders",
    over=state_path("orders"),
    as_="order",
)
charge = graph.use(
    charge_order,
    input=[input_from(orders.item, "order")],
)
graph.set_route(orders, "loop", charge)
graph.set_route(charge, "ok", orders)
```

Normal capabilities receive foreach values through declared inputs. Advanced
handlers may inspect `ctx.foreach["orders"].index` and stable runtime
identities. Child workflows do not inherit caller context and must receive
input. `loop_item`, `loop_index`, and aliases are migration conveniences.

Read [references/python-lifecycle.md](references/python-lifecycle.md) when a
complete typed lifecycle or an editing/debugging recipe is needed.
