# Workflow Artifacts

This document captures the current design direction for saved workflows. It is a
design note, not an implementation status document.

## Ownership Boundary

Saved workflows are not inherently MCP concerns. `wf_mcp` is one capability
provider and one client/proxy surface; it should not become the owner of
workflow artifact storage, deployments, schedules, run history, and UI policy.

Preferred conceptual stack:

```text
wf_core
  execution model, runtime, validation

wf_authoring
  ergonomic builders, @node, reusable ops

wf_mcp
  MCP adapters, proxying, catalogs, connection auth

wf_artifacts
  immutable saved workflow definitions, versions, dependency contracts

wf_platform
  deployments, bindings, schedules, run history, UI/admin policy
```

The project does not need all of these as separate packages immediately, but
new names and docs should preserve the split. `wf_mcp` may host early
experiments when it is the first consumer, but the domain model should point
toward extraction rather than making MCP the center of the workflow platform.

`wf_mcp` may expose workflow artifacts to an LLM client, but only as a
projection over an artifact/platform service. It should not own artifact state.

Prefer a small stable MCP control surface over dynamically adding one MCP tool
per saved workflow:

```text
wf.workflow.list_artifacts
wf.workflow.inspect_artifact
wf.workflow.validate_deployment
wf.workflow.run_deployment
```

This is important because MCP clients may not reliably refresh `tools/list` when
new workflow artifacts are saved. More specifically, LLM harnesses may refresh
or display a changed tool list without rebuilding the callable tool schema used
for the current model turn. A stable `run_deployment` tool lets an LLM test saved
workflows immediately without requiring dynamic tool registration or tool-list
notifications to work perfectly.

This control surface should not fork between backend service layers. The public
server now has one exposure style, but internally it still combines:

- service-backed local workflow/admin tools
- upstream proxy projection through MCP `tools/list` and `tools/call`

Workflow artifact operations should be defined once and projected through the
server surface instead of owning separate workflow registries or separate run
semantics.

Dynamic projection of saved workflows as individual MCP tools can exist later,
but it should be optional. The stable run tool is the reliable base layer.

For long-running workflow execution, prefer MCP-native execution mechanisms
where available:

- `notifications/progress` for progress updates while a request is still active
- MCP Tasks for call-now/fetch-later execution when the client and server
  negotiate task support

Do not invent a separate `start` convention as the primary MCP shape if MCP
Tasks are available. A compatibility tool such as `wf.workflow.start_run` can be
added later for clients that do not support Tasks, but that should be treated as
a fallback platform API rather than the preferred MCP contract.

## Terms

### Workflow Artifact

A workflow artifact is a saved, validated workflow package. It is more than a
raw workflow JSON document because it needs enough metadata for reuse,
inspection, dependency checks, and migration.

Expected shape:

```text
WorkflowArtifact
  id
  title
  description
  version
  input_schema
  output_schema
  outcomes
  plan
  required_sources
  created_from_catalog_version
```

Workflow artifact versions are immutable. Once a version is saved, its plan,
schemas, declared outcomes, and dependency declarations do not change in place.
Repairs and migrations should create a new artifact version or an external
binding decision rather than rewriting the old version.

Artifacts should prefer logical source aliases over concrete connection ids.
For example, a saved workflow can require `context7.query-docs` while a
deployment binding maps `context7` to `context7.default` or
`context7.team_account`. This gives saved workflows dependency injection for MCP
capability sources.

Logical source aliases are part of the immutable artifact. Concrete source
bindings are deployment/runtime configuration.

In this context, an account means an MCP connection profile with its own auth
and catalog behavior. It does not imply multiple users of the workflow app. A
single operator may connect several MCP accounts and bind deployments to
different accounts.

### Saved Workflow As Node

A saved workflow can be projected as a workflow node spec. At the parent
workflow boundary it behaves like a node:

- one input schema
- one output schema
- multiple declared outcomes
- interrupt points discovered from declared interrupt nodes
- nested trace preservation

Internally, it still runs as a graph with its own nodes, state, frames, traces,
foreach behavior, and interrupts.

The public boundary should match what an ordinary node provides. Parent
workflows should depend on the saved workflow's declared input schema, output
schema, outcomes, and required logical sources. Internal child graph structure
is not part of the public contract.

`interrupt_kinds` is a likely future boundary field, but it is not part of the
current schema yet. Until then, interrupts should still bubble with trace/path
metadata at runtime without becoming a declared schema field.

Current core interrupt semantics are node-level. An `InterruptNode` has:

- `kind`
- `request_map`, mapping state/input/context paths to public interrupt payload
  fields
- `out_map`, mapping resume payload fields back into state
- declared resume `outcomes`

That means an artifact can document interrupt boundaries by scanning its
declarative plan for interrupt nodes and deriving their request/resume payload
schemas from the maps and workflow state/input schemas. It should not need to
store unrelated child graph internals just to describe the public interrupt
points.

## Composition Rule

LLMs and users should compose saved workflows from the catalog as ordinary node
specs, for example:

```text
workflow.summarize_docs.v1
  input_schema: ...
  output_schema: ...
  outcomes: done, needs_input, failed
```

The authoring surface should not require the LLM to write Python. It should use
declarative workflow artifacts plus validation feedback.

Saved workflows need two projections:

- NodeSpec-shaped catalog entries for composition
- full artifact records for inspection, debugging, repair, and migration

The NodeSpec-shaped projection is what a planner or LLM should use by default:

```text
workflow.summarize_docs.v1
  input_schema
  output_schema
  outcomes
  description
  required_sources
  diagnostics
```

The full artifact projection exposes the declarative plan, dependency contract
snapshots, deployments, bindings, and validation diagnostics. This is for
humans, migration tools, and advanced LLM repair flows.

Default composition should not require the client to inspect internal graph
details.

The declarative graph plan is the canonical saved form. Compiled or runtime
forms are disposable caches:

```text
WorkflowArtifact
  plan: declarative workflow graph
  compiled_cache: optional, disposable
```

If a compiled cache is missing or stale, rebuild it from the plan. Do not treat
compiled state as the source of truth.

Workflow steps should reference catalog capabilities by logical name and keep
contract snapshots separately. Do not inline full executable node specs into
every step.

```text
step:
  node_ref: context7.query-docs

required_capabilities:
  context7.query-docs:
    kind: tool
    input_schema_hash
    input_schema_snapshot
    output_schema_hash
    output_schema_snapshot
```

This is similar to import resolution. The artifact stores stable logical
imports. The deployment binds those imports to concrete sources. Dependency
validation checks that the concrete source still satisfies the recorded
contract.

## Dependency Rule

Workflow artifacts depend on capability sources. If a required source is removed,
disabled, or no longer exposes the needed capability, the workflow artifact must
remain visible but become unrunnable.

Unrunnable artifacts should return dependency diagnostics rather than disappear:

```text
workflow: workflow.summarize_docs.v1
status: unrunnable
missing_dependencies:
  - source: context7.default
    capability: context7.default.query_docs
    reason: source disabled
```

Diagnostics should be structured and machine-readable:

```text
DependencyDiagnostic
  severity: error | warning
  code: source_missing | source_disabled | capability_missing | schema_changed | binding_missing
  logical_ref
  bound_source
  message
  repair_hint
```

Structured diagnostics let tests, dashboards, and LLM clients handle dependency
failures without parsing human-readable error strings.

This preserves repairability:

- users can inspect the saved workflow
- LLMs can explain what broke
- dashboards can offer rebind/restore actions
- future migration tools can map old sources to new ones

The artifact definition is immutable, but dependency status is live. A workflow
version can move between runnable and unrunnable as the surrounding capability
sources change.

Dependency checks should validate bindings, not just names. A concrete source
can satisfy a logical source alias only when it still exposes a compatible
capability contract.

Artifacts should store a dependency contract snapshot for each capability they
actually use:

```text
RequiredCapability
  logical_source: context7
  capability_name: query-docs
  kind: tool
  input_schema
  output_schema
  observed_concrete_source: context7.default
  observed_at
```

The snapshot is not a full catalog pin. It is the minimum contract needed to
detect whether the currently bound source still satisfies the saved workflow.

Workflow artifacts may depend on other workflow artifacts. A parent stores only
its direct dependencies; it should not copy a child workflow's dependency
snapshots into itself. Runtime/deployment validation walks the transitive
dependency graph and reports the chain that failed.

```text
answer_question
  depends on search_docs
    depends on context7.query-docs
```

If `context7.query-docs` breaks, `answer_question` is unrunnable because
`search_docs` is unrunnable. Diagnostics should preserve that chain.

Saved workflow dependencies should start with exact artifact-version pins:

```text
direct_dependency:
  workflow: search_docs
  version: 3
```

Exact pins make saved workflow behavior reproducible. Leave room for a future
`version_constraint` field if a semver parser is added, but do not start with
floating latest-compatible behavior.

Workflow artifact dependencies must be acyclic. Reject dependency cycles during
save or deployment validation, before runtime execution.

```text
dependency_cycle:
  chain: workflow.a@1 -> workflow.b@2 -> workflow.a@1
```

Cycles should be rejected even if branch logic appears to make them unreachable.
The static dependency graph must stay acyclic so validation, tracing, and future
resume behavior remain understandable.

Dependency validation happens in two phases.

At save time:

```text
validate graph shape
resolve logical references
record required contracts
reject obviously invalid workflows
```

At deployment or run time:

```text
resolve concrete bindings
check source enabled or missing
compare current contracts to recorded contracts
apply drift_policy
return diagnostics or run
```

Save-time validation proves that the artifact was valid when created.
Deployment/run-time validation proves that the current environment can still
satisfy it.

Important dependency failure cases:

- source missing: the configured MCP connection no longer exists
- source disabled: the user or admin turned off the source
- capability missing: the source exists but no longer exposes the required tool,
  prompt, resource, or node spec
- capability changed: the source still exposes the capability but its schema or
  behavior no longer matches the artifact's recorded expectation

Missing and disabled sources are hard unrunnable failures. Capability changes
should start as diagnostics and become hard failures when the recorded schema is
no longer compatible with the saved workflow boundary.

Initial compatibility checks can be conservative:

- exact input/output schema hash match: compatible
- missing source: unrunnable
- missing capability: unrunnable
- new required input fields: unrunnable
- removed input fields that the workflow sends: unrunnable
- changed fields that downstream workflow paths read: unrunnable
- description/title/metadata-only changes: warning
- unknown or changed-but-not-proven-incompatible schema: follow deployment drift
  policy

## Binding Rule

Use binding when the workflow intent stays the same but the concrete source
changes:

```text
artifact reference: context7.query-docs
runtime binding:    context7 -> context7.default
```

or:

```text
artifact reference: context7.query-docs
runtime binding:    context7 -> context7.team_account
```

Use migration when the graph, mappings, schemas, outcomes, or intended provider
semantics change. Migration creates a new immutable workflow artifact version.

The practical split:

- rebind: same capability contract, different concrete source
- migrate: changed workflow behavior, incompatible schema, or different
  provider semantics

Bindings should live outside the immutable artifact, preferably on a deployment
or run configuration:

```text
WorkflowDeployment
  artifact_id: summarize_docs
  artifact_version: 1
  deployment_id: summarize_docs.context7_default
  bindings:
    context7: context7.default
  drift_policy: block
```

The default binding scope is deployment-level. A per-run override can be added
later for interactive or one-off runs. Bindings should not be modeled as
per-user until the application actually has user accounts and tenancy.

A deployment id identifies one configured way to run an artifact version. Two
deployments can point at the same immutable workflow artifact while binding
logical sources to different MCP accounts or connection profiles:

```text
deployment: summarize_docs.personal
artifact:   summarize_docs@1
bindings:
  context7: context7.personal

deployment: summarize_docs.work
artifact:   summarize_docs@1
bindings:
  context7: context7.work
```

This gives the stable MCP run tool a concrete target without requiring one MCP
tool per workflow or account.

Recommended drift-policy defaults:

- scheduled/offline deployments: `block`
- manual interactive runs: `warn`
- development runs: `warn` or `allow`

This prevents silent scheduled failures while still allowing local repair and
experimentation.

## Storage Direction

Workflow artifacts should use a store protocol rather than baking filesystem
paths into the models. The existing `wf_mcp.storage.Store` persists auth and
catalog snapshots; workflow artifacts have a different lifecycle, so start with
a sibling artifact-store protocol instead of immediately expanding the MCP store
interface.

Expected shape:

```text
WorkflowArtifactStore
  save_artifact(artifact)
  get_artifact(id, version)
  list_artifacts()
  resolve_latest(id)
```

The initial implementation can be file-backed and share the same root directory
family as the existing MCP store:

```text
.wf_mcp_store/
  auth/
  catalog/
  workflows/
    summarize_docs/
      1.json
      2.json
```

Keeping the store behind a protocol makes it straightforward to move artifacts
to SQLite, Postgres, or another backend later.

## Runtime Direction

Saved workflow execution eventually needs first-class runtime support for:

- nested run state
- child-frame trace preservation
- interrupt bubbling with path metadata
- resume into child run state
- child final outcome mapping to parent node outcome
- dependency checks before execution
- reducer capabilities referenced by declared workflow state fields are saved as
  direct artifact dependencies just like node specs or tools; reducer config is
  part of the state field contract, while the dependency key is the reducer name

Runtime execution must resolve reducer dependencies, not just validate that they
exist. A deployment binding maps the artifact's logical reducer source, such as
`custom`, to a concrete source, such as `custom.default`. The runtime registers
the concrete `ReducerDefinition` under the logical reducer name used in the
saved workflow state schema, such as `custom.multiply`. This keeps artifact
plans stable while allowing deployments to choose concrete accounts or local
reducer packages.

Node specs may also use deployment-bound logical names. A saved plan can refer
to `demo.echo_tool`, while the deployment binds `demo` to a concrete source such
as `demo.personal`. At runtime the compiler builds node definitions from the
concrete source but leaves the saved artifact immutable. Concrete node names
such as `demo.personal.echo_tool` remain supported for raw local plans and older
artifacts.

Implementation note: these references are currently parsed from strings with
dot-separated source and capability names. That keeps the wire format simple but
leaks path logic into runtime code. A future cleanup should introduce typed
reference objects, such as `CapabilityRef(logical_source, capability_name)` and
`BoundCapabilityRef(concrete_source, capability_name)`, and leave dot-joined
strings as presentation and serialization only.

The first implementation should prefer artifact validation and dependency
diagnostics before attempting persistent nested resume.

Native subgraphs are not in `wf_core` yet. The current core `Step` model has
node, condition, foreach, join, and interrupt steps, but no subgraph step. The
current `wf_authoring.subgraph_node` helper executes a child workflow as a plain
node and validates the child output. Future saved-workflow-as-node execution
needs a real child run state if child interrupts should pause the parent and
later resume the child.

Until that core upgrade exists, artifact tooling must not assume that an
interrupting saved workflow can safely be used as a child node. Top-level saved
workflows with interrupt nodes are valid, but nested interrupting workflows
should be reported as unsupported for composition.

Blocking dependency failures happen before workflow execution and are not normal
workflow outcomes. A missing source, disabled source, unresolved binding, or
incompatible capability contract means the deployment is unrunnable.

```text
validate deployment dependencies
if blocking diagnostics exist:
  return unrunnable dependency diagnostics
else:
  run workflow
```

Dependency diagnostics may be shown to parent workflows, dashboards, and LLM
clients, but they should not be routed through ordinary business outcomes such
as `failed`.

MCP tool result errors are different from dependency failures. A generated MCP
tool wrapper can expose generic outcomes such as `ok` and `error`; workflow
authors must wire both outcomes explicitly. A `runtime_error` node is a valid
way to terminate generic tool errors.

Richer business outcomes should be modeled with wrapper graph-nodes rather than
by making every generated MCP node guess domain semantics. For example, a
workflow can wrap a raw MCP call and map result content to outcomes such as
`found`, `not_found`, `unauthorized`, or `rate_limited` when those meanings are
known for that tool.

## Open Questions

- How should child workflow interrupts compose with parent workflow execution
  once saved workflows can run as real subgraphs instead of plain node wrappers?
