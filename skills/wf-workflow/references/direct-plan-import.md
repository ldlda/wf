# Direct Plan Import Reference

Use direct plan import only when you already have a complete workflow plan. For
interactive authoring, prefer draft workspaces and focused edit commands.

Before writing a plan, inspect the current public shape:

    wf schema raw
    wf schema NodeUse
    wf schema InputPathBinding
    wf schema OutputBinding

Use `wf schema raw --verbose` only when the complete validation schema is
required.

## Command Path

```bash
wf artifact create-from-plan workflow.plan.json \
  --artifact <artifact_id> \
  --version 1 \
  --title "Workflow Title" \
  --outcome ok \
  --binding <logical_source>=<concrete_source>

wf deploy save <deployment_id> \
  --artifact <artifact_id> \
  --version 1 \
  --binding <logical_source>=<concrete_source>

wf deploy validate <deployment_id>
wf run start <deployment_id> --input-file input.json
```

The `--binding` on `artifact create-from-plan` records required logical sources
on the artifact. The `--binding` on `deploy save` makes the deployment runnable.
For non-platform sources, use both unless a command explicitly says otherwise.

## Complete Plan Shape

The plan file is the low-level workflow model. It is not a draft workspace.

```json
{
  "name": "example_workflow",
  "input_schema": {
    "type": "object",
    "properties": {
      "text": { "type": "string" }
    },
    "required": ["text"]
  },
  "state_schema": {
    "type": "object",
    "properties": {
      "notes": { "type": "string", "reducer": "wf.std.replace" },
      "report": { "type": "object", "reducer": "wf.std.replace" }
    }
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "report": { "type": "object" }
    },
    "required": ["report"]
  },
  "outcomes": ["ok"],
  "start": "read",
  "nodes": [
    {
      "id": "read",
      "type": "node",
      "node": "example.source.read",
      "input": [
        {
          "path": "input.text",
          "target": "text"
        }
      ],
      "output": [
        {
          "source": "text",
          "target": "state.notes"
        }
      ]
    },
    {
      "id": "extract",
      "type": "node",
      "node": "example.source.extract",
      "input": [
        {
          "path": "state.notes",
          "target": "text"
        }
      ],
      "output": [
        {
          "source": ".",
          "target": "state.report"
        }
      ]
    }
  ],
  "edges": [
    { "from": "read", "outcome": "ok", "to": "extract" },
    { "from": "extract", "outcome": "ok", "to": "__end__" }
  ],
  "output": [
    {
      "path": "state.report",
      "target": "report"
    }
  ]
}
```

## Field Rules

- Top level uses `nodes` and `edges`, not draft `steps` and `routes`.
- Each node object uses `"node": "<capability_name>"`, not draft field `use`.
- Node input mappings use `path -> target`.
- Node output mappings use `source -> target`.
- Top-level workflow output mappings use `path -> target`.
- `__end__` is the terminal edge target.
- Reducers live in `state_schema.properties.<field>.reducer`.

## Common Mistakes

- Use `wf draft create <workspace_id> --capability <capability>` for draft creation.
- Do not pass draft JSON to `artifact create-from-plan`.
- Do not omit deployment bindings for ordinary sources. Platform sources such
  as `wf.std` may be omitted or self-bound, but configured sources usually need
  explicit deployment bindings.
