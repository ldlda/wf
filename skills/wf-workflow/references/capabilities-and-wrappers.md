# Capabilities And Wrappers Reference

Use this when deciding whether to call a capability directly, wrap it, or place
it in a workflow.

## Core Split

```text
raw MCP tool != workflow capability
```

A raw MCP tool may be callable and still be awkward for workflows. Workflow
capabilities are graph-facing contracts with schemas and outcomes.

## Discovery Order

1. Use `wf source list` or `wf status` when source ownership is unclear.
2. Use `wf cap list --format ids` for graph-ready capabilities.
3. Use `wf cap inspect <capability>` for one full contract.
4. Use `wf cap call <capability>` to test a single workflow-facing contract.

## Wrapper Artifacts

Use a wrapper artifact when the raw provider shape needs normalization:

- provider status strings should become workflow outcomes
- raw envelopes should be narrowed
- `isError` or error blocks need explicit outcome routing
- provider inputs are too broad or unstable for graph use

Saved wrappers appear as workflow capabilities under source id `workflow`, with
names like `workflow.echo_wrapper.v1`.

## Wrapper Hints

`inspect_capability` returns `wrapper_hints`. Treat them as authoring
scaffolding:

- `confidence=high`: simple shape, likely safe to validate first
- `confidence=medium`: usable but review candidates
- `confidence=low`: patch missing decisions before saving

`next_actions` is guidance, not validation authority.

## MCP Content Blocks

MCP tools often return `content: [{type, text, ...}]`. Do not map this list
into a string state field. Filter/extract text explicitly, or write a wrapper
that decides what content types are acceptable.

If a result exposes a convenience `text` field, inspect the capability schema
and wrapper hints before using it. Do not assume every content block is text.

Incorrect:

```json
{"source": "content", "target": "state.summary"}
```

Correct: filter `content` to text blocks, extract each `text`, then combine or
select the value before writing it to a string state field.
