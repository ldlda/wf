# Workflow Capabilities

This document separates the things an MCP-facing platform can expose from the
things a workflow should usually consume.

The short version:

```text
raw capability != workflow capability
```

An MCP tool may be callable and still be a poor workflow node until someone
wraps it into a cleaner workflow-facing contract.

## Core Terms

### Source

A source is a named owner of capabilities.

Examples:

- `everything.default`: an upstream MCP connection source
- `wf.std`: the local workflow standard library
- `wf.mcp`: local workflow helpers for interacting with MCP backends
- `wf.admin`: privileged control-plane capabilities

A source is **not** defined by one protocol. MCP connection sources commonly
own tools, prompts, and resources. Local sources may own only node specs, or
node specs plus documentation prompts/resources, or only privileged admin
tools.

The source answers:

```text
who owns this capability?
```

not:

```text
what protocol transported it?
```

### Raw Capability

A raw capability is what a source directly provides.

Examples:

- an upstream MCP tool
- an upstream MCP prompt
- an upstream MCP resource
- a local admin tool
- a local standard-library helper

Raw capabilities are useful for direct inspection and direct invocation, but
their interface is shaped by the provider. That provider-facing interface may
not be pleasant or safe for workflow composition.

### Workflow Capability

A workflow capability is a workflow-facing `NodeSpec`.

Today, a `NodeSpec` has:

- one input schema
- one output schema
- one or more named outcomes

It does **not** currently support a different output schema per outcome.

The workflow capability answers:

```text
how should a graph use this thing?
```

instead of:

```text
how did the original provider happen to expose this thing?
```

### Wrapper / Adapter Artifact

A wrapper artifact is a saved reusable bridge from a raw capability to a
workflow capability.

Examples:

- convert a raw `isError` result into workflow outcomes such as `ok` and
  `error`
- map a provider-specific `status` field into workflow outcomes such as
  `needs_input`, `done`, and `failed`
- strip a provider result envelope and expose only the data a graph should use
- normalize awkward parameter names or output shapes for repeated workflow use

A wrapper artifact is useful when a human or LLM has learned once how to make a
provider capability workflow-friendly and should not have to rediscover that
interpretation every time.

Expected properties:

- saved
- inspectable
- reusable
- dependency-aware
- directly testable before use in a graph

### Workflow Artifact

A workflow artifact is a saved graph.

It may depend on:

- workflow capabilities from local sources
- generated workflow wrappers around upstream tools
- saved wrapper artifacts authored earlier
- other saved workflow artifacts later, once graph-as-node is real

### Deployment

A deployment binds a saved workflow artifact to concrete runtime sources.

This is where logical source names can resolve to concrete accounts or
connections, for example:

```text
context7 -> context7.default
```

or later:

```text
crm -> salesforce.work
```

## Why Raw MCP Tools Are Not Automatically Good Workflow Nodes

MCP tools are general callable capabilities. Workflow nodes need contracts that
compose well inside graphs.

Common mismatch examples:

### Status Encoded In Output

A provider may return:

```json
{
  "status": "needs_input",
  "message": "pick one"
}
```

A workflow usually wants an explicit outcome:

```text
needs_input
```

so the graph can branch without every downstream node re-parsing provider
status strings.

### Error Encoded By Transport Convention

An MCP tool call has protocol-level success/error handling. A workflow often
wants errors represented as explicit graph outcomes that must be wired.

### Provider Envelopes

A provider may return:

```json
{
  "ok": true,
  "data": {
    "items": [...]
  }
}
```

while the graph wants:

```json
{
  "items": [...]
}
```

### Human-Friendly Versus Graph-Friendly Inputs

A raw tool may be good for interactive human use but awkward for stateful graph
composition. A wrapper can expose the small stable interface the graph actually
needs.

## Generated Versus Authored Workflow Capabilities

Some workflow capabilities can be generated mechanically:

- a simple MCP tool whose result already maps cleanly to one output schema and
  `ok` / `error` outcomes

Others should be authored and saved:

- tools with domain-specific status fields
- tools whose raw shape is too provider-centric
- tools whose result needs durable semantic interpretation

The platform should support both.

## Authoring Loop

A client authoring workflows, including an LLM client, should be able to:

1. inspect available sources
2. inspect raw capabilities
3. inspect existing workflow capabilities and saved wrappers
4. call a workflow capability directly once
5. inspect the normalized output and outcome
6. reuse that capability inside a graph

That direct-call surface is different from:

- calling the raw upstream MCP tool
- running a full workflow artifact
- using privileged admin tools

It exists so authors can test the workflow-facing contract before composing it.

## Relationship To Capability Sources

Sources own capability kinds:

```text
tools
node_specs
prompts
resources
```

Possible later additions may include saved wrappers or workflow artifacts as
first-class projected capability kinds, but they should not erase the raw versus
workflow-facing distinction.

Examples:

- `everything.default.tools["search"]`
  - raw upstream capability
- `everything.default.node_specs["everything.default.search"]`
  - generated workflow-facing wrapper, if the raw tool maps cleanly
- `user.crm.lookup_customer`
  - saved authored wrapper around a raw upstream tool, if the original contract
    needed interpretation

## Current System Truth

Today:

- `CapabilitySource` already owns buckets for tools, node specs, prompts, and
  resources
- connection sources represent upstream MCP snapshots
- `wf.std` owns local reusable workflow node specs
- `wf.mcp` owns workflow-facing MCP runtime helpers
- discovered upstream tools can already become workflow node specs

Not yet implemented:

- a saved wrapper artifact model
- a direct public tool for calling arbitrary workflow node specs for authoring
  tests
- per-outcome output schemas
- graph-as-node for saved workflows

These are separate next steps. The current model should leave room for them
without pretending they already exist.
