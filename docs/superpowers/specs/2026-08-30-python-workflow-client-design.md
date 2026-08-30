# Python Workflow Client Design

## Status

Approved in conversation on 2026-08-30. This document specifies the public
Python object model; it does not authorize implementation until its companion
implementation plan is reviewed.

## Purpose

Add a public `wf_client` package for humans, IPython sessions, and AI agents
that have Python execution available. The package reconstructs workflow API
responses into useful Python objects, supports local graph authoring with
remote capabilities, saves immutable workflow versions through the existing
API, and operates deployments and runs without exposing JSON-RPC payloads.

This is not a new workflow backend. It is a deep Python interface over the
existing workflow API surface, HTTP JSON-RPC adapter, domain models, and
`WorkflowBuilder`.

## Design Principles

- `App` is the only connection entry point users need to learn.
- Network operations are async. A synchronous facade is allowed only if it can
  be implemented without owning or nesting an event loop.
- Local graph mutations are synchronous; remote discovery, saving, deployment,
  and execution are async.
- JSON serialization exists only at the transport seam. Public objects contain
  validated domain values, not unchecked response dictionaries.
- Existing `wf_core`, `wf_artifacts`, and `wf_authoring` models remain the
  source of truth. `wf_client` must not create parallel workflow semantics.
- Workflow artifacts remain immutable. Editing creates a mutable graph seeded
  from an exact artifact version.
- Deployments remain explicit when source selection matters and become
  conditional ceremony when no binding choice exists.
- Capability nodes and native subgraphs remain distinct authoring operations.
- Draft workspaces do not appear in the public `wf_client` interface.

## Hypothetical Usage

This section is the intended experience. Names may tighten during
implementation, but the lifecycle and amount of required ceremony are part of
the design contract.

### Connect and use one capability

```python
from wf_client import App

app = App.from_http_jsonrpc("http://localhost:8765/rpc")

search = await app.capability("app.default.search")

print(search.input_schema)
result = await search(query="durable workflow systems")
print(result.outcome)
print(result.output)
```

`search` is a validated Python object, not an RPC response dictionary. Calling
it validates input locally, uses the workflow capability operation, validates
the response, and returns a `CapabilityResult`.

### Build, save, and run a workflow

```python
from pydantic import BaseModel, Field

from wf_authoring import input_from, input_path, output_to, state_path
from wf_client import App


class ReportInput(BaseModel):
    topic: str


class ReportState(BaseModel):
    sources: list[str] = Field(default_factory=list)


class ReportOutput(BaseModel):
    sources: list[str]


app = App.from_http_jsonrpc("http://localhost:8765/rpc")
search = await app.capability("app.default.search")

graph = app.new_workflow(
    "report",
    input_schema=ReportInput,
    state_schema=ReportState,
    output_schema=ReportOutput,
)

searched = graph.use(
    search,
    id="search",
    input=[input_from(input_path("topic"), "query")],
    output=[output_to("sources", state_path("sources"))],
)
done = graph.end("ok", id="end_ok")

graph.set_entry_point(searched)
graph.connect(searched, "ok", done)
graph.set_output([input_from(state_path("sources"), "sources")])

report_v1 = await graph.save(version=1, title="Research report")
run = await report_v1.run({"topic": "durable workflow systems"})

print(run.status)
print(run.output)
```

`graph` is an `EditableWorkflow`, which subclasses `WorkflowBuilder`. Existing
builder operations such as `use()`, `when()`, `choose()`, `match()`,
`foreach()`, `interrupt()`, `end()`, `connect()`, and `set_entry_point()` remain
available directly. `wf_client` adds remote-capability use, provenance,
lossless workflow output bindings, and `save()`.

The convenient `artifact.run()` form is available only when source bindings
are already unambiguous. It never chooses between accounts.

### Bind an environment explicitly

```python
production = await report_v1.deploy(
    "report.production",
    bindings={
        "app.default": "company.production",
    },
)

validation = await production.validate()
if not validation.runnable:
    for diagnostic in validation.diagnostics:
        print(diagnostic.message)
else:
    run = await production.run({"topic": "durable workflow systems"})
```

Artifacts describe logical source requirements. Deployments select the actual
configured sources for an environment. Built-in platform-only workflows need
little or no deployment ceremony.

### Edit an immutable saved version

```python
report_v2_graph = await app.edit_workflow("report", version=1)
summarize = await app.capability("app.default.summarize")

summarized = report_v2_graph.use(summarize, id="summarize")
report_v2_graph.set_route("search", "ok", summarized)
report_v2_graph.connect(summarized, "ok", "end_ok")

report_v2 = await report_v2_graph.save(version=2)
```

Version 1 remains unchanged. `edit_workflow()` validates the artifact and its
plan, then seeds the same builder methods with every schema, node, edge,
binding, outcome, and subgraph reference preserved.

### Reuse a saved workflow as a native subgraph

```python
parent = app.new_workflow(
    "weekly_digest",
    input_schema=DigestInput,
    state_schema=DigestState,
    output_schema=DigestOutput,
)

report_step = parent.subgraph(
    report_v2,
    input=[input_from(input_path("topic"), "topic")],
    output=[output_to("sources", state_path("report_sources"))],
)
```

An ordinary remote capability uses `graph.use(capability)`. An immutable saved
workflow uses `graph.subgraph(artifact)`. The distinction remains visible
because their dependency and runtime semantics differ.

### Resume an interrupted run

```python
run = await report_v2.run({"topic": "durable workflow systems"})

if run.interrupt is not None:
    print(run.interrupt.request)
    run = await run.resume({"approved": True})

for frame in (await run.trace(limit=25)).frames:
    print(frame.node_id, frame.outcome)
```

Rich representations may summarize these objects in IPython, but displaying an
object never performs I/O or executes a capability.

## Public Package

```text
src/wf_client/
├── __init__.py
├── app.py
├── authoring.py
├── capabilities.py
├── codec.py
├── deployments.py
├── errors.py
├── protocols.py
├── runs.py
└── workflows.py
```

Responsibilities:

- `app.py`: connection construction and top-level discovery.
- `protocols.py`: the narrow internal port consumed by rich client objects.
- `codec.py`: wire payload to existing domain-model validation.
- `capabilities.py`: remote capability inspection and invocation.
- `authoring.py`: editable graph composition over `WorkflowBuilder`.
- `workflows.py`: immutable artifact and editable-workflow lifecycle.
- `deployments.py`: deployment validation and execution.
- `runs.py`: run refresh, trace, interrupt, and resume.
- `errors.py`: stable structured Python exceptions.

The existing `RpcWorkflowApiClient` is the production HTTP adapter for the
internal port. Tests use an in-memory adapter over the process-local workflow
API. Transport operation strings do not appear outside adapters.

## Python Protocols

The following declarations describe the intended public behavior. Concrete
classes may contain private state and helper methods not shown here.

```python
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol, Self

type JsonObject = dict[str, Any]
type JsonSchema = JsonObject
type DriftPolicy = Literal["block", "warn", "allow"]


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    artifact_id: str
    version: int


@dataclass(frozen=True, slots=True)
class CapabilityRef:
    source: str
    capability_key: str


class App:
    @classmethod
    def from_http_jsonrpc(
        cls,
        url: str,
        *,
        timeout_seconds: float = 30.0,
    ) -> Self: ...

    async def capability(self, name: str) -> RemoteCapability: ...

    async def capabilities(
        self,
        *,
        query: str | None = None,
        source_id: str | None = None,
        limit: int = 50,
    ) -> Page[CapabilitySummary]: ...

    def new_workflow(
        self,
        name: str,
        *,
        input_schema: SchemaLike,
        state_schema: StateSchemaLike,
        output_schema: SchemaLike,
        outcomes: Sequence[str] = ("ok",),
    ) -> EditableWorkflow: ...

    async def workflow(
        self,
        artifact_id: str,
        *,
        version: int,
    ) -> WorkflowArtifact: ...

    async def edit_workflow(
        self,
        artifact_id: str,
        *,
        version: int,
    ) -> EditableWorkflow: ...

    async def deployment(self, deployment_id: str) -> Deployment: ...

    async def run(self, run_id: str) -> Run: ...
```

`App.from_http_jsonrpc()` configures a transport adapter but does not perform
network I/O. Returned objects retain the internal client port so their remote
methods do not require callers to pass `App` repeatedly.

### Remote capability

```python
class RemoteCapability:
    ref: CapabilityRef
    qualified_name: str
    description: str | None
    input_schema: JsonSchema
    output_schema: JsonSchema
    outcomes: tuple[str, ...]
    is_async: bool

    async def __call__(
        self,
        payload: Mapping[str, Any] | None = None,
        /,
        **fields: Any,
    ) -> CapabilityResult: ...

    async def call(
        self,
        payload: Mapping[str, Any],
        *,
        deployment_id: str | None = None,
    ) -> CapabilityResult: ...


@dataclass(frozen=True, slots=True)
class CapabilityResult:
    outcome: str
    output: JsonObject | None
    diagnostics: tuple[Diagnostic, ...]
```

The callable shorthand accepts one positional mapping or keyword fields, never
both. The explicit `call()` method carries advanced client options so a real
capability input field named `deployment_id` remains unambiguous. Inputs are
validated against the inspected capability schema before transport. Output and
outcome are validated against the inspected contract after transport.

`RemoteCapability` is not a local `NodeSpec`: it has no process-local handler.
The authoring adapter consumes its reference and schema contract directly.

### Editable workflow

```python
class EditableWorkflow(WorkflowBuilder):
    name: str
    based_on: ArtifactRef | None

    def use(
        self,
        capability: RemoteCapability,
        *,
        id: str | None = None,
        input: Sequence[StepInputBindingArg] | None = None,
        output: Sequence[OutputBindingArg] | None = None,
        desc: str | None = None,
    ) -> NodeUse: ...

    def subgraph(
        self,
        workflow: WorkflowArtifact,
        *,
        id: str | None = None,
        input: Sequence[StepInputBindingArg] | None = None,
        output: Sequence[OutputBindingArg] | None = None,
        desc: str | None = None,
    ) -> SubgraphNode: ...

    def set_entry_point(self, step: StepRef) -> None: ...
    def connect(self, source: StepRef, outcome: str, target: StepRef) -> None: ...

    def set_route(
        self,
        source: StepRef,
        outcome: str,
        target: StepRef,
    ) -> None: ...

    def remove_route(self, source: StepRef, outcome: str) -> None: ...
    def remove_step(self, step: StepRef) -> None: ...

    def set_output(
        self,
        bindings: Sequence[StepInputBindingArg],
    ) -> None: ...

    def validate(self) -> ValidationReport: ...
    def compile(self) -> Workflow: ...

    async def save(
        self,
        *,
        artifact_id: str | None = None,
        version: int,
        title: str | None = None,
        description: str | None = None,
    ) -> WorkflowArtifact: ...
```

`EditableWorkflow` subclasses `WorkflowBuilder` from the separate `wf_client`
package. `WorkflowBuilder` stays transport-free, while the subclass inherits
its full authoring interface and adds remote-capability adaptation, artifact
provenance, and saving through the connected client port. Do not copy builder
methods into a parallel wrapper and do not use dynamic `__getattr__`
delegation; both approaches would create typing and drift problems.

Seeded editing also requires focused `set_route()`, `remove_route()`, and
`remove_step()` mutations. `set_route()` replaces the unique edge for one
source/outcome pair rather than appending a duplicate. `remove_step()` rejects
removal while routes still reference the step, so callers must deliberately
rewire or remove those routes first. These are local builder operations, not
draft API calls.

`set_output()` must first become a lossless `WorkflowBuilder` operation.
`compile()` must preserve workflow output bindings. This repair is required
before artifact editing is exposed.

`use()` accepts `RemoteCapability`; `subgraph()` accepts a workflow artifact.
These methods are intentionally not overloaded into one operation because a
capability call and a native subgraph boundary have different execution,
dependency, and trace semantics.

### Workflow artifact

```python
class WorkflowArtifact:
    ref: ArtifactRef
    title: str
    description: str | None
    workflow: Workflow
    required_capabilities: tuple[RequiredCapability, ...]
    workflow_dependencies: Mapping[str, int]

    def inspect(self) -> Workflow: ...
    def edit(self) -> EditableWorkflow: ...

    async def deploy(
        self,
        deployment_id: str,
        *,
        bindings: Mapping[str, str] | None = None,
        drift_policy: DriftPolicy = "block",
    ) -> Deployment: ...

    async def run(
        self,
        input: Mapping[str, Any],
        *,
        deployment_id: str | None = None,
        bindings: Mapping[str, str] | None = None,
        drift_policy: DriftPolicy = "block",
    ) -> Run: ...
```

`edit()` is local because the artifact already holds its validated workflow.
It seeds a new editable workflow without mutating the artifact.

Convenience `run()` follows strict policy:

1. Use `deployment_id` when supplied.
2. Otherwise use an existing unambiguous default deployment if the backend
   exposes one.
3. Otherwise create or reuse an implicit deployment only when every dependency
   is platform-provided or has one unambiguous concrete binding.
4. Otherwise raise `DeploymentRequired` with unresolved logical sources and
   candidate bindings.

The client never guesses between accounts or environments.

### Deployment and run

```python
class Deployment:
    deployment_id: str
    artifact: ArtifactRef
    bindings: Mapping[str, str]
    drift_policy: DriftPolicy
    diagnostics: tuple[Diagnostic, ...]
    runnable: bool

    async def validate(self) -> DeploymentValidation: ...
    async def run(self, input: Mapping[str, Any]) -> Run: ...


class Run:
    run_id: str
    deployment_id: str
    status: Literal["running", "interrupted", "completed", "failed"]
    outcome: str | None
    output: JsonObject | None
    interrupt: Interrupt | None
    diagnostics: tuple[Diagnostic, ...]

    async def refresh(self) -> Self: ...
    async def resume(self, response: Mapping[str, Any]) -> Self: ...
    async def trace(self, *, start: int = 0, limit: int = 25) -> TracePage: ...
```

Methods that change remote lifecycle state return refreshed immutable
snapshots. They do not mutate a Python object behind the caller's back.

## Data Flow

Capability discovery:

```text
App.capability(name)
  -> client port.inspect_capability(name)
  -> JSON-RPC adapter
  -> wire response validation
  -> RemoteCapability
```

Authoring and saving:

```text
EditableWorkflow local mutations
  -> WorkflowBuilder.compile()
  -> core Workflow validation
  -> JSON-compatible plan at the adapter seam
  -> workflow.artifacts.create_from_plan
  -> WorkflowArtifact reconstruction
```

Editing:

```text
App.workflow(ref)
  -> inspect artifact
  -> WorkflowArtifact model validation
  -> Workflow model validation from artifact.plan
  -> WorkflowArtifact.edit()
  -> lossless EditableWorkflow seeded from Workflow
```

## Serialization Boundary

HTTP JSON-RPC necessarily serializes requests and responses. The client must
localize that fact:

```text
public/domain object
  <-> codec using existing Pydantic/domain models
  <-> transport DTO
  <-> JSON-RPC adapter
```

The current RPC mixins use static `cast()` calls over unchecked dictionaries.
The new package must not repeat that pattern. The adapter or codec validates
each operation result before a public object is constructed. Invalid server
responses raise `InvalidResponse` with the operation name and validation
details.

## Error Model

`wf_client` exposes structured exceptions rooted at `WorkflowClientError`:

```python
class WorkflowClientError(Exception): ...
class TransportError(WorkflowClientError): ...
class ProtocolError(WorkflowClientError): ...
class InvalidResponse(ProtocolError): ...
class CapabilityNotFound(WorkflowClientError): ...
class ArtifactNotFound(WorkflowClientError): ...
class ArtifactVersionConflict(WorkflowClientError): ...
class DeploymentRequired(WorkflowClientError): ...
class DeploymentNotRunnable(WorkflowClientError): ...
class ValidationFailed(WorkflowClientError): ...
class RevisionConflict(WorkflowClientError): ...
```

The HTTP adapter preserves the server error code, structured data, and repair
information. Rich client objects translate only stable workflow errors; unknown
server codes remain inspectable `ProtocolError` instances.

## IPython Representation

Rich objects provide concise `repr()` output. `_repr_html_()` is allowed for
capabilities, workflows, deployments, and runs when it displays only bounded,
already-loaded state. Representation must never trigger network I/O, execute a
capability, expose secrets, or fetch an unbounded trace.

## Draft Boundary

`wf_client` does not import draft models or expose draft methods. Direct Python
authoring compiles a complete workflow and saves it through the existing
artifact-from-plan operation.

Making draft support uninitialized by default is a separate server-composition
slice. Today `WorkflowApi` constructs draft modules unconditionally, durable
context validation requires a draft store, and the JSON-RPC app always
registers draft methods. That follow-up must make draft storage, domain modules,
and RPC registration opt-in without weakening artifact, deployment, or run
durability.

## Testing Strategy

Tests exercise the same public interface callers use:

- Contract tests run `App` against an in-memory client-port adapter.
- HTTP integration tests run `App.from_http_jsonrpc()` against the local ASGI
  JSON-RPC application.
- Capability tests cover inspection, schema validation, direct calls, and graph
  use.
- Round-trip tests require exact preservation of schemas, nodes, edges, step
  bindings, workflow output bindings, outcomes, and subgraph references across
  artifact inspection, editing, compilation, and saving.
- Deployment tests cover implicit platform-only execution, explicit bindings,
  ambiguous binding rejection, drift diagnostics, and run creation.
- Run tests cover completed output, failure, interrupt inspection, resume, and
  bounded trace reads.
- Error tests prove structured server errors survive the HTTP adapter.
- Representation tests prove `repr()` and `_repr_html_()` perform no I/O and
  redact bounded fields where necessary.

## Delivery Slices

1. Repair lossless builder workflow-output and `Workflow` reconstruction.
2. Add the internal client port, codecs, and structured errors.
3. Add `App` and callable `RemoteCapability`.
4. Add `EditableWorkflow` and artifact save/inspect/edit round trips.
5. Add `Deployment`, `Run`, and strict convenience execution.
6. Add bounded IPython representations and user documentation.
7. Separately make draft server composition opt-in and disabled by default.

Each slice must be independently tested and preserve the existing low-level
RPC adapter for CLI and compatibility callers.

## Out of Scope

- Scheduling or cron semantics.
- Deleting draft implementation.
- A synchronous facade that manages event loops.
- Dynamic Python source registration.
- Generating Python classes from arbitrary JSON Schema.
- UI authoring changes.
- Changing workflow runtime execution semantics.
- Automatically choosing among multiple concrete source accounts.
