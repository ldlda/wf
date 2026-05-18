# Workflow Drafts

Workflow drafts are the preferred authoring format for LLM and human clients.

They sit above the raw `Workflow` model:

```text
WorkflowDraft -> RawWorkflowPlan -> WorkflowArtifact -> Deployment
```

The draft format is intentionally explicit and patchable. It avoids asking an
LLM client to write the full core model directly, while still compiling into the
same validated workflow plan used by the runtime.

Raw plans still exist as an escape hatch for advanced clients and compiler
outputs. New authoring flows should normally start with drafts.

## Why Drafts Exist

The raw workflow model is normalized for execution. That makes it precise, but
not always pleasant as an interactive authoring target.

Drafts optimize for:

- stable JSON shapes that are easy to inspect
- explicit step ids instead of implicit Python object references
- targeted fixes through JSON Patch
- a clear place to validate before saving
- preserving the existing raw workflow/runtime boundary

Drafts do not change workflow semantics. They compile into the same core plan
shape and then run through normal validation.

## Draft Shape

A minimal draft looks like this:

```json
{
  "name": "echo",
  "input_schema": {
    "type": "object",
    "properties": {
      "text": {
        "type": "string"
      }
    },
    "required": ["text"]
  },
  "state_schema": {
    "fields": {
      "echoed": {
        "type": "string"
      }
    }
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "echoed": {
        "type": "string"
      }
    },
    "required": ["echoed"]
  },
  "start": "echo",
  "steps": [
    {
      "id": "echo",
      "kind": "use",
      "capability": "demo.personal.echo_tool",
      "in": {
        "input.text": "text"
      },
      "out": {
        "echoed": "state.echoed"
      }
    }
  ],
  "edges": [
    {
      "from": "echo",
      "outcome": "ok",
      "to": "__end__"
    }
  ]
}
```

Important details:

- `steps[].id` is required because JSON has no Python object identity.
- `start` names a step id.
- `edges[].to` can name another step id or `__end__`.
- `capability` may be concrete during exploration, such as
  `demo.personal.echo_tool`.
- When saved with source bindings, concrete refs can be normalized to logical
  refs such as `demo.echo_tool`.

## Step Kinds

### `use`

Calls a workflow capability.

```json
{
  "id": "echo",
  "kind": "use",
  "capability": "demo.personal.echo_tool",
  "in": {
    "input.text": "text"
  },
  "out": {
    "echoed": "state.echoed"
  }
}
```

Use this for normal node calls, including generated workflow wrappers around
MCP tools and local `wf.std` capabilities.

### `condition`

Evaluates a condition and routes by outcome.

```json
{
  "id": "has_text",
  "kind": "condition",
  "check": {
    "op": "exists",
    "args": ["input.text"]
  }
}
```

Condition nodes compile to graph nodes with condition semantics. Their outgoing
edges should use condition outcomes such as `true` and `false`.

### `foreach`

Runs a child body over items.

```json
{
  "id": "each_item",
  "kind": "foreach",
  "over": "state.items",
  "as": "item",
  "mode": "serial",
  "on_item_error": "fail"
}
```

Use `serial` unless the runtime explicitly supports a parallel async path for
the target workflow.

### `interrupt`

Declares an interrupting step.

```json
{
  "id": "ask_user",
  "kind": "interrupt",
  "interrupt_kind": "input",
  "request": {
    "state.question": "question"
  },
  "resume": {
    "answer": "state.answer"
  },
  "outcomes": ["resumed", "cancelled"]
}
```

Saved interrupting artifacts are still limited in the current execution
surface. If a deployment reports `interrupting_artifact_unsupported`, that is a
known platform limitation rather than a draft bug.

### `join`

Joins control flow.

```json
{
  "id": "join_results",
  "kind": "join"
}
```

## Draft Tools

The workflow MCP surface exposes these draft tools:

| Tool | Purpose |
| --- | --- |
| `wf.workflow.validate_draft` | Validate draft shape and compiled workflow without saving. |
| `wf.workflow.compile_draft` | Return the compiled raw plan plus dependency summaries. |
| `wf.workflow.patch_draft` | Apply RFC 6902 JSON Patch and validate the patched draft. |
| `wf.workflow.create_artifact_from_draft` | Compile, normalize, and save a workflow artifact. |

Use `validate_draft` before saving. Use `patch_draft` when an LLM client needs a
small targeted correction instead of rewriting the whole workflow.

## Patching Drafts

`patch_draft` accepts JSON Patch operations.

Example:

```json
[
  {
    "op": "replace",
    "path": "/steps/0/in/input.text",
    "value": "message"
  },
  {
    "op": "add",
    "path": "/edges/-",
    "value": {
      "from": "echo",
      "outcome": "error",
      "to": "__end__"
    }
  }
]
```

Patch the draft, not the compiled raw plan. The raw plan is an implementation
boundary and may be harder for an LLM client to repair correctly.

## Saving And Running

The normal path is:

```text
wf.workflow.validate_draft
wf.workflow.create_artifact_from_draft
wf.workflow.save_deployment
wf.workflow.validate_deployment
wf.workflow.run_deployment
```

`create_artifact_from_draft` may return suggested bindings for local system
sources such as:

```json
{
  "wf.std": "wf.std",
  "wf.mcp": "wf.mcp"
}
```

Keep those explicit when deployment validation reports `binding_missing`.

## Raw Plan Escape Hatch

Use `wf.workflow.create_artifact_from_plan` only when the caller already has a
compiled raw workflow plan or is intentionally bypassing the draft layer.

For normal interactive authoring, prefer:

```text
draft -> validate -> patch if needed -> create artifact from draft
```

That keeps errors local and gives the author a smaller object to reason about.

## Read Next

- [`wf_mcp_operator_manual.md`](wf_mcp_operator_manual.md) for the MCP-facing
  tool family map
- [`wf_mcp_end_to_end_runbook.md`](wf_mcp_end_to_end_runbook.md) for a complete
  connection-to-run example
- [`workflow_capabilities.md`](workflow_capabilities.md) for raw capability
  versus workflow capability
- [`workflow_artifacts.md`](workflow_artifacts.md) for artifacts, deployments,
  and dependency contracts
