# Authoring Layer Sketch

This document sketches the next layer on top of `wf_core`.

The goal is to make workflow authoring pleasant for:

- Python developers using `@node`
- builder-style graph construction
- client LLMs that consume a node catalog and emit graph structure

This layer should compile down to the existing core model without changing
runtime semantics.

## Principles

1. `wf_core` remains the execution model.
2. Authoring APIs compile to `wf_core.Workflow`.
3. `NodeDef` should usually be derived, not written manually.
4. The LLM should usually choose from a node catalog, not invent raw node defs.
5. Generics belong at the authoring boundary, not in the runtime core.

## Main Objects

### `NodeSpec[InputT, OutputT]`

The durable product of `@node`.

Responsibilities:

- hold typed Python callable metadata
- expose input and output model types
- expose node outcomes
- generate a core `NodeDef`
- register a runtime handler
- remain directly callable in Python

This should be the single central wrapper object. Avoid creating multiple
parallel wrapper types with overlapping meanings.

### `WorkflowBuilder`

Builder API for human Python authors.

Responsibilities:

- collect node uses
- collect control-flow nodes
- collect edges
- derive unique `NodeDef`s from referenced `NodeSpec`s
- compile to a core `Workflow`

Typical entry points:

- `use(node_spec, id=..., in_map=..., out_map=...)`
- `condition(...)`
- `foreach(...)`
- `interrupt(...)`
- `connect(...)`
- `compile()`

### `NodeCatalog`

LLM-facing registry of available nodes.

Responsibilities:

- expose name, docs, schemas, and outcomes
- provide a normalized machine-readable view for MCP consumers
- allow the client LLM to build `NodeUse`s against known nodes

The client LLM should usually receive a node catalog and emit graph structure
that references those known nodes. It should not usually generate new raw
`NodeDef`s.

## Flow

### Python authoring flow

1. declare `InputModel` and `OutputModel`
2. decorate a function with `@node(...)`
3. receive a `NodeSpec`
4. add `NodeSpec`s to a `WorkflowBuilder`
5. compile builder to core `Workflow`
6. build a registry from the same `NodeSpec`s
7. run with existing runtime

### LLM graph authoring flow

1. MCP exposes a `NodeCatalog`
2. client LLM selects nodes from the catalog
3. client LLM emits graph structure:
   - node uses
   - mappings
   - conditions
   - foreach nodes
   - interrupt nodes
   - edges
4. server compiles or validates that structure into core `Workflow`
5. runtime executes core `Workflow`

## Docs and schema descriptions

Input and output models should prefer `pydantic.BaseModel`.

Recommended sources of documentation:

- class docstring: model-level description
- `Field(description=...)`: strongest field-level description
- attribute docstrings with `ConfigDict(use_attribute_docstrings=True)`: good authoring UX

The authoring layer should normalize these into schema descriptions so MCP can
surface them to client LLMs.

## Async stance

Do not hide async behind `.result()`.

Preferred design:

- `NodeSpec` knows whether a callable is sync or async
- sync runtime accepts sync handlers
- future async runtime accepts async handlers

If sync runtime encounters an async node, fail clearly rather than faking a sync
bridge.

## Async runtime seam

The intended async work should be additive, not a rewrite.

Recommended shape:

- keep current sync runtime as the stable baseline
- add async siblings instead of mutating the sync path into a mixed mode
- avoid hidden sync-to-async or async-to-sync bridges in core execution

Likely async entry points:

- `execute_workflow_async(...)`
- `resume_workflow_async(...)`
- `step_workflow_async(...)`
- `execute_node_use_async(...)`

Likely registry split:

- sync registry: `dict[str, SyncNodeHandler]`
- async registry: `dict[str, AsyncNodeHandler]`

`NodeSpec` should support both export paths:

- `to_registry_handler()` for sync callables only
- `to_async_registry_handler()` for sync or async callables
- `build_registry(...)` for sync specs
- `build_async_registry(...)` for mixed or async specs

This keeps the rules simple:

- sync runtime executes sync handlers only
- async runtime can execute both sync and async handlers
- async runtime is the natural home for future MCP-backed tool nodes

## MCP proxy layer

MCP integration should sit above `wf_core`, not inside it.

Recommended layering:

1. MCP client or proxy code discovers tools
2. each MCP tool is wrapped as a `NodeSpec`
3. wrapped specs enter the same `NodeCatalog` as handwritten nodes
4. the client LLM builds graphs against one unified catalog
5. workflows compile to the existing core `Workflow`
6. runtime executes registry handlers without caring whether the backing tool is local Python or MCP

This means MCP tools should look like ordinary nodes at the authoring boundary:

- declared input model
- declared output model
- declared outcomes
- description/docs for LLM consumption
- sync or async execution capability

The proxy/MCP layer should be responsible for:

- tool discovery
- schema translation
- auth/session concerns
- wrapping tool calls into `NodeSpec`s

The core runtime should remain responsible only for:

- mapping input/state/context into node payloads
- validating payloads
- routing outcomes
- writing mapped output into workflow state
- interrupts, frames, trace, and foreach semantics

## Type validation stance

Current core validation is intentionally shallow. Today it mainly enforces:

- object payloads are dict-like
- required keys exist

It does not yet fully enforce:

- scalar field types
- nested object structure
- array item types
- enums/literals

Near-term recommendation:

- keep `SchemaRef` as the portable contract/export shape
- keep using `pydantic.BaseModel` as the strongest validation layer for authored nodes
- gradually strengthen core schema validation where it pays off

This is especially useful for MCP wrapping, because the proxy layer can often
normalize a tool contract into Pydantic models before the workflow runtime sees
it.

## Future extension

### `Workflow -> NodeSpec`

In the future, a compiled workflow or subgraph can be wrapped as a reusable
`NodeSpec`, likely by treating workflow input and output schemas as the node's
input and output schemas.

That should be an authoring-layer transformation, not a core runtime rewrite.
