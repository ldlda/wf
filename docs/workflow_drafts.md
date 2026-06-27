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
    "type": "object",
    "properties": {
      "echoed": {
        "type": "string",
        "reducer": "wf.std.replace"
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
  "steps": {
    "echo": {
      "use": "demo.personal.echo_tool",
      "input": [
        {
          "target": "text",
          "path": "input.text"
        }
      ],
      "output": [
        {
          "source": "echoed",
          "target": "state.echoed"
        }
      ]
    }
  },
  "routes": {
    "echo": {
      "ok": "__end__"
    }
  }
}
```

Important details:

- `steps` are keyed by stable ids so patches do not depend on array positions.
- `start` names one step id.
- `routes` map step outcomes to another step id or `__end__`.
- top-level `outcomes` declares public workflow terminal outcomes; if omitted,
  it defaults to `["ok"]`.
- top-level `output` maps final graph values such as `state.result` into the
  public workflow output payload. Step-level `output` only writes a node result
  into workflow state.
- `capability` may be concrete during exploration, such as
  `demo.personal.echo_tool`.
- When saved with source bindings, concrete refs can be normalized to logical
  refs such as `demo.echo_tool`.

## Two Outputs, Different Shapes

Drafts have two fields named `output`, but they do different jobs.

### Step-Level `steps.<id>.output`

Step output writes a node's local return payload into workflow state. It uses
`source` / `target`:

```json
{
  "source": "text",
  "target": "state.result_text"
}
```

Read this as:

```text
node output.text -> state.result_text
```

### Top-Level `output`

Top-level workflow output projects graph values into the final public workflow
output payload. It uses input-binding shape: `path` / `target`, not
`source` / `target`. Do not use step output `source` here; it belongs to
step-level node output bindings only.

```json
{
  "path": "state.result_text",
  "target": "result_text"
}
```

Read this as:

```text
state.result_text -> workflow output.result_text
```

If top-level `output` is empty, the runtime keeps the legacy same-name fallback:
for every field in `output_schema`, it copies the top-level state field with the
same name when present. That fallback is convenient, but explicit output
projection is clearer for new workflows.

## Explicit Outputs And Error Outcomes

Use `__end__` as the compact terminal path for the normal `ok` workflow outcome.
For any other public terminal outcome, add an explicit `end` step and route to
it. The end step itself is terminal; do not add an edge out of it.

This complete draft shape:

```json
{
  "name": "echo_with_error",
  "input_schema": {
    "type": "object",
    "properties": {
      "text": { "type": "string" },
      "fail": { "type": "boolean" }
    },
    "required": ["text"]
  },
  "state_schema": {
    "type": "object",
    "properties": {
      "raw": {
        "type": "object",
        "properties": {
          "echoed": { "type": "string" }
        }
      }
    }
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "message": { "type": "string" }
    }
  },
  "outcomes": ["ok", "error"],
  "output": [
    {
      "target": "message",
      "path": "state.raw.echoed"
    }
  ],
  "start": "call",
  "steps": {
    "call": {
      "use": "demo.echo",
      "input": [
        {
          "target": "text",
          "path": "input.text"
        },
        {
          "target": "fail",
          "path": "input.fail"
        }
      ],
      "output": [
        {
          "source": "echoed",
          "target": "state.raw.echoed"
        }
      ]
    },
    "end_error": {
      "end": { "outcome": "error" }
    }
  },
  "routes": {
    "call": {
      "ok": "__end__",
      "error": "end_error"
    }
  }
}
```

Read it as:

- `call.ok` finishes the workflow with outcome `ok`.
- `call.error` executes `end_error`, which finishes the workflow with outcome
  `error`.
- both terminal paths project `state.raw.echoed` into public output field
  `message`.

## Binding Shape

Draft `use` steps use the same canonical binding structs as core `NodeUse`:

```json
{
  "input": [
    {
      "target": "message",
      "path": "input.text"
    },
    {
      "target": "limit",
      "value": 3
    }
  ],
  "output": [
    {
      "source": "echoed",
      "target": "state.echoed"
    }
  ]
}
```

Legacy draft maps `in`, `with`, and `out` are still accepted as parse-only
compatibility input. Valid drafts are saved and returned with canonical
`input` and `output` binding lists.

Graph source paths in `in` normally start with `input.`, `state.`, or
`context.`. Node-local paths do not use those prefixes; they are paths inside
the target capability's input or output payload.

In canonical string paths, segments are joined with dots. For nested objects,
use `"input.user.name"`. For literal dots in property names, use TOML quoting:
`state."person.name"`.

For example, this canonical input/output pair:

```json
{
  "input": [
    {
      "target": "user.name",
      "path": "input.user.name"
    },
    {
      "target": "job.title",
      "path": "state.job.title"
    }
  ],
  "output": [
    {
      "source": "user.age",
      "target": "state.person.age"
    },
    {
      "source": "job.years",
      "target": "state.experience.years"
    }
  ]
}
```

Read that as:

- `input.user.name` -> local input `user.name`
- `state.job.title` -> local input `job.title`
- local output `user.age` -> `state.person.age`
- local output `job.years` -> `state.experience.years`

Do not reverse the direction. This is wrong:

```json
{
  "input": [
    {
      "target": "input.text",
      "path": "message"
    }
  ]
}
```

That asks the runtime to read from graph path `message` and write into a
node-local input field literally named `input.text`.

Do not put constants in path bindings. This is wrong:

```json
{
  "input": [
    {
      "target": "value",
      "path": "input.CLICKED"
    }
  ]
}
```

Use an input value binding for static node-local values instead.

## Step Kinds

### `use`

Calls a workflow capability.

```json
{
  "use": "demo.personal.echo_tool",
  "input": [
    {
      "target": "text",
      "path": "input.text"
    }
  ],
  "output": [
    {
      "source": "echoed",
      "target": "state.echoed"
    }
  ]
}
```

Use this for normal node calls, including generated workflow wrappers around
MCP tools and local `wf.std` capabilities.

`use` steps can also provide static node-local input values.
Use this for hardcoded strings, booleans, numbers, and small JSON values that
are part of the graph definition:

```json
{
  "use": "wf.std.constant",
  "input": [
    {
      "target": "value",
      "value": "CLICKED"
    }
  ],
  "output": [
    {
      "source": "value",
      "target": "state.wait_text"
    }
  ]
}
```

Static values are not path mappings. Use `{"target": ..., "value": ...}` for
literal JSON values. Invalid draft step shapes are rejected instead of silently
compiling to `join`.

Generated MCP tool wrappers are intentionally naive. They normally expose both
`ok` and `error` outcomes, because MCP tool calls can report transport/provider
errors separately from useful output. Drafts should wire both outcomes:

```json
{
  "routes": {
    "call_tool": {
      "ok": "__end__",
      "error": "tool_error"
    }
  }
}
```

Use a wrapper node or `wf.std.runtime_error` for the `error` path. Do not leave
the generated `error` outcome dangling.

### `foreach`

Runs a child body over items. Draft foreach mirrors the core foreach policy
model: use `item_error` and `concurrent`, not draft-only field names.

```json
{
  "foreach": {
    "over": "state.items",
    "as": "item",
    "mode": "serial",
    "item_error": "fail"
  }
}
```

Concurrent foreach uses the same canonical policy shape as core:

```json
{
  "foreach": {
    "over": "state.items",
    "as": "item",
    "mode": "concurrent",
    "concurrent": {
      "max_active": 2,
      "max_outstanding": 4
    },
    "item_error": {
      "action": "collect",
      "collect_to": "state.item_errors"
    }
  }
}
```

`item_error` accepts `"fail"` and `"skip"` as shorthand. `collect` needs an
explicit destination, so `item_error: "collect"` is invalid; use the object
shape and provide `collect_to`. Deprecated `on_item_error` and `parallel` are
accepted only as parse-only compatibility and dump back to canonical fields.

### `interrupt`

Declares an interrupting step.

```json
{
  "interrupt": {
    "kind": "input",
    "request": [
      {
        "target": "question",
        "path": "state.question"
      }
    ],
    "resume": [
      {
        "source": "answer",
        "target": "state.answer"
      }
    ],
    "outcomes": ["resumed", "cancelled"]
  }
}
```

Draft interrupts use the same binding shapes as core interrupt nodes:
`request` builds the public interrupt payload, while `resume` maps the payload
provided on resume back into workflow state. Older map-shaped `request` and
`resume` values are accepted only as parse compatibility and dump back to the
canonical list shape.

Saved interrupting artifacts can pause and resume through deployment runs. The
run response includes a durable `run_id`; pass that to
`wf.workflow.resume_run` with the resume payload. Before advancing a resumed
run, the platform revalidates its pinned dependency environment and can return
`resume_readiness="blocked"` without consuming input.

### `end`

Declares an explicit workflow terminal outcome.

```json
{
  "end": {
    "outcome": "error"
  }
}
```

Use explicit `end` steps for non-`ok` workflow outcomes. The legacy `__end__`
destination remains the shorthand for public workflow outcome `ok`.

### `join`

Joins control flow.

```json
{
  "join": {}
}
```

### `when`

Creates one boolean decision step. The condition uses the same JSON shape as
`wf_core.models.conditions.Condition`.

```json
{
  "when": {
    "if": {
      "op": "ge",
      "left": {
        "path": "state.count"
      },
      "right": {
        "value": 1
      }
    },
    "then": "positive",
    "otherwise": "zero"
  }
}
```

The draft adapter lowers this through `WorkflowBuilder.when()`. The draft step
id becomes the generated condition entry id, so other routes can target it.

### `match`

Matches one graph value against ordered equality cases.

```json
{
  "match": {
    "value": "state.status",
    "cases": [
      {
        "equals": "ready",
        "then": "run"
      },
      {
        "equals": "waiting",
        "then": "pause"
      }
    ],
    "default": "__end__"
  }
}
```

Cases are a list rather than a JSON object so values such as `1`, `"1"`, and
`true` are not silently coerced into object keys. The draft adapter lowers this
through `WorkflowBuilder.match()`.

### `choose`

Creates an ordered first-true decision chain.

```json
{
  "choose": {
    "clauses": [
      {
        "if": {
          "op": "gt",
          "left": {
            "path": "state.score"
          },
          "right": {
            "value": 80
          }
        },
        "then": "high"
      },
      {
        "if": {
          "op": "exists",
          "path": "state.fallback"
        },
        "then": "fallback"
      }
    ],
    "default": "__end__"
  }
}
```

`choose` lowers through `WorkflowBuilder.choose()` and expands to generated
condition nodes. `match`, `when`, and `choose` replace the deprecated `route()`
concept for draft JSON; there is intentionally no draft `route` step kind.

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

## Draft Workspaces

Stateless draft tools require the caller to resend the whole draft. Draft
workspaces are the preferred LLM authoring flow when a client will patch a
workflow over several turns.

The workspace flow is:

1. `wf.workflow.create_minimal_draft_workspace`
2. `wf.workflow.get_draft_workspace`
3. `wf.workflow.patch_draft_workspace`
4. repeat get/patch until valid
5. `wf.workflow.create_artifact_from_workspace` for a full workflow, or
   `wf.workflow.create_wrapper_from_workspace` for a reusable callable wrapper

Workspaces are mutable and revisioned. Artifacts are immutable and versioned.
Patch calls must include the current `revision`; stale revisions return
`revision_conflict` and do not mutate the workspace.

`create_minimal_draft_workspace` is intentionally only a bootstrapper. For
naive MCP wrappers with an `error` outcome, it wires `wf.std.runtime_error` with
a static default message unless `error_message_source` is explicitly provided.
It does not guess that a normal output state path is also an error message.
Provider-specific error envelopes still belong in saved wrapper artifacts or
follow-up patches.

`error_message_source` accepts the same canonical string path shape used by
other mapping fields, for example `"state.error_message"`. Legacy structural
shapes remain accepted for compatibility.

In MCP Inspector, workspace mutation tools accept a single `request` object.
This is deliberate: the request object carries descriptions and validation for
the authoring envelope while raw JSON Schema fields remain plain JSON objects.

`create_wrapper_from_workspace` is intentionally just the wrapper-specific save
path. It validates and compiles the same draft workspace, but fixes the saved
artifact kind to `wrapper` so clients do not need to pass `kind` manually.

## Focused Edit Commands

For routine edits, prefer focused commands over hand-written JSON Patch:

```bash
wf draft set-name <workspace_id> --revision <n> --name <name>
wf draft set-route <workspace_id> --revision <n> --step <step_id> --outcome ok --to <target_step_or___end__>
wf draft set-input <workspace_id> --revision <n> --step <step_id> --map input.text=text
wf draft set-output <workspace_id> --revision <n> --step <step_id> --map text=state.text
```

Use `draft patch` when these focused commands do not cover the structural edit.

Drafts are not raw workflow plans. Drafts use `steps`, `routes`, and step field
`use`. Raw plans use `nodes`, `edges`, and node field `node`.

## Patching Drafts

`patch_draft` accepts JSON Patch operations.

Example:

```json
[
  {
    "op": "replace",
    "path": "/steps/echo/in/input.text",
    "value": "message"
  },
  {
    "op": "add",
    "path": "/routes/echo/error",
    "value": "__end__"
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
