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

## Future extension

### `Workflow -> NodeSpec`

In the future, a compiled workflow or subgraph can be wrapped as a reusable
`NodeSpec`, likely by treating workflow input and output schemas as the node's
input and output schemas.

That should be an authoring-layer transformation, not a core runtime rewrite.
