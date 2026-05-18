# wf_mcp End-To-End Runbook

This runbook shows one complete successful path through the platform:

```text
configured connection
  -> refreshed catalog
  -> source/capability discovery
  -> direct capability test
  -> saved workflow artifact
  -> saved deployment
  -> validated deployment
  -> deployment run
```

The example uses an imaginary upstream MCP connection:

```text
demo.personal
```

which exposes one workflow-ready capability:

```text
demo.personal.echo_tool
```

The saved artifact uses the logical source alias `demo`, so the same workflow can
later be deployed against `demo.work` or another compatible account.

## 0. Know The Three Names

This example deliberately uses three related names:

| Name | Meaning |
| --- | --- |
| `demo.personal` | concrete configured connection/source |
| `demo.personal.echo_tool` | concrete discovered workflow capability |
| `demo.echo_tool` | logical capability ref stored in the saved artifact |

The deployment later binds:

```json
{
  "demo": "demo.personal"
}
```

That is the important separation between reusable workflow definition and
concrete account choice.

## 1. Add Or Confirm The Connection

If the connection does not exist yet:

```yaml
tool: wf.admin.add_connection
arguments:
{
  "connection_id": "demo.personal",
  "server": "demo",
  "account": "personal",
  "metadata": {
    "transport": "stdio",
    "command": "python",
    "args": ["path/to/demo_server.py"]
  }
}
```

If it already exists, inspect the configured set:

```yaml
tool: wf.admin.list_connections
arguments: {}
```

Expected idea:

```json
[
  {
    "id": "demo.personal",
    "server": "demo",
    "account": "personal",
    "enabled": true
  }
]
```

## 2. Refresh The Upstream Catalog

```yaml
tool: wf.admin.refresh_connection_catalog
arguments:
{
  "connection_id": "demo.personal"
}
```

This is the discovery step. It asks the upstream MCP server what it currently
exposes and updates the stored catalog snapshot.

After this succeeds, these views become useful:

```yaml
tool: wf.admin.get_catalog
arguments: {}
```

for the raw upstream MCP snapshot, and:

```yaml
tool: wf.admin.get_planner_catalog
arguments: {}
```

for the planner-facing node-spec view.

Prefer the progressive-discovery tools below for ordinary use; full catalogs can
be large.

## 3. Discover The Source

First list compact source summaries:

```yaml
tool: wf.admin.list_sources
arguments:
{
  "limit": 20
}
```

Then inspect only the source you care about:

```yaml
tool: wf.admin.inspect_source
arguments:
{
  "source_id": "demo.personal"
}
```

You want to confirm:

- the source is enabled
- it is planner-visible
- it owns the expected generated node spec / workflow capability

## 4. Discover And Inspect The Workflow Capability

Find the workflow-ready capability:

```yaml
tool: wf.workflow.list_capabilities
arguments:
{
  "source_id": "demo.personal",
  "query": "echo",
  "limit": 20
}
```

The list response is intentionally compact. It includes `source_id`, outcomes,
and top-level `input_fields` / `output_fields`, but not full JSON schemas.

Then inspect its full contract:

```yaml
tool: wf.workflow.inspect_capability
arguments:
{
  "qualified_name": "demo.personal.echo_tool"
}
```

This is where you learn:

- input schema
- output schema
- declared outcomes
- whether it is async
- whether it is actually a good workflow-facing contract

## 5. Test The Capability Directly

Before composing a workflow, call the node contract once:

```yaml
tool: wf.workflow.call_capability
arguments:
{
  "qualified_name": "demo.personal.echo_tool",
  "payload": {
    "text": "hello"
  }
}
```

Expected shape:

```json
{
  "outcome": "ok",
  "output": {
    "echoed": "hello"
  }
}
```

This is the authoring REPL step. It tests the workflow-facing contract, not just
the raw upstream MCP tool call.

## 6. Save A Workflow Artifact

Create a one-node workflow that:

- accepts `input.text`
- calls the discovered echo capability
- stores `echoed` into workflow state
- ends on the node's `ok` outcome

```yaml
tool: wf.workflow.create_artifact_from_draft
arguments:
{
  "artifact_id": "echo",
  "version": 1,
  "title": "Echo",
  "outcomes": ["completed"],
  "source_bindings": {
    "demo": "demo.personal"
  },
  "draft": {
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
    "steps": {
      "echo": {
        "use": "demo.personal.echo_tool",
        "in": {
          "input.text": "text"
        },
        "out": {
          "echoed": "state.echoed"
        }
      }
    },
    "routes": {
      "echo": {
        "ok": "__end__"
      }
    }
  }
}
```

Important behavior:

- because `source_bindings` says `"demo": "demo.personal"`, the saved artifact
  is normalized to logical node ref `demo.echo_tool`
- the saved dependency contract records what was observed from
  `demo.personal.echo_tool` at creation time
- the draft is compiled into a raw workflow plan and validated before saving

Inspect the saved result if needed:

```yaml
tool: wf.workflow.inspect_artifact
arguments:
{
  "artifact_id": "echo",
  "version": 1
}
```

## 7. Save A Deployment

Artifacts are reusable definitions. Deployments decide which concrete sources
run them.

```yaml
tool: wf.workflow.save_deployment
arguments:
{
  "deployment": {
    "id": "echo.personal",
    "artifact_id": "echo",
    "artifact_version": 1,
    "bindings": {
      "demo": "demo.personal",
      "wf.std": "wf.std"
    }
  }
}
```

The `wf.std` self-binding is present when the saved graph depends on standard
library capabilities. This tiny echo graph does not need much from `wf.std`, but
keeping local system-source bindings explicit is the current general pattern.

System-source bindings can look redundant:

```json
{
  "wf.std": "wf.std",
  "wf.mcp": "wf.mcp"
}
```

They mean "bind the artifact's logical local source to the concrete local source
with the same id." They are not external account bindings. Keep them explicit
for now when validation reports `binding_missing` for `wf.std` or `wf.mcp`.
Later the platform may make system-source self-bindings implicit, but current
artifacts and deployments use one uniform binding mechanism for both local and
external sources.

## 8. Validate Before Running

```yaml
tool: wf.workflow.validate_deployment
arguments:
{
  "deployment_id": "echo.personal"
}
```

You want a runnable result with no blocking diagnostics.

Validation catches problems such as:

- a bound source is disabled or missing
- a required capability disappeared
- the saved dependency schema snapshot drifted from the live capability

## 9. Run The Deployment

```yaml
tool: wf.workflow.run_deployment
arguments:
{
  "deployment_id": "echo.personal",
  "workflow_input": {
    "text": "hello"
  }
}
```

Expected shape:

```json
{
  "status": "completed",
  "output": {
    "echoed": "hello"
  },
  "diagnostics": [],
  "trace_count": 1
}
```

## 10. Rebind The Same Artifact Later

If another compatible account appears:

```text
demo.work
```

you do **not** need to rewrite artifact version `1`.

Create another deployment:

```json
{
  "id": "echo.work",
  "artifact_id": "echo",
  "artifact_version": 1,
  "bindings": {
    "demo": "demo.work",
    "wf.std": "wf.std"
  }
}
```

Then validate it. If `demo.work.echo_tool` is compatible with the saved contract,
the same workflow artifact can run there.

## Full Minimal Sequence

For a client that already has an enabled connection, the normal minimal flow is:

```text
wf.admin.refresh_connection_catalog
wf.admin.list_sources
wf.workflow.list_capabilities
wf.workflow.inspect_capability
wf.workflow.call_capability
wf.workflow.validate_draft
wf.workflow.create_artifact_from_draft
wf.workflow.save_deployment
wf.workflow.validate_deployment
wf.workflow.run_deployment
```

## Common Failure Points

### The connection exists but nothing is discoverable

Check:

1. `wf.admin.list_connections`
2. `wf.admin.refresh_connection_catalog`
3. `wf.admin.inspect_source`

A configured connection can exist with zero loaded capabilities until refresh
succeeds.

### The upstream server has tools but no prompts/resources

That is valid. `resources/list` and `prompts/list` are optional MCP families.
A tools-only server should still refresh successfully.

### The raw proxy tool is callable but not pleasant in a graph

That is the raw-tool versus workflow-capability distinction. Use or build a
workflow-facing wrapper when the raw tool's shape is provider-centric.

### The draft is close but has one wrong field

Use `wf.workflow.patch_draft` instead of asking the client to rewrite the whole
workflow. Draft patching uses JSON Patch and revalidates the patched result.

### The deployment used to run but now fails validation

Likely causes:

- source disabled
- capability removed
- schema drift from the saved dependency snapshot

Inspect:

```text
wf.admin.inspect_source
wf.workflow.inspect_artifact
wf.workflow.validate_deployment
```

## Read Next

- [`wf_mcp_operator_manual.md`](wf_mcp_operator_manual.md) for the short mental
  model and tool-family map
- [`wf_mcp_troubleshooting.md`](wf_mcp_troubleshooting.md) for non-happy-path
  discovery and deployment failures
- [`workflow_capabilities.md`](workflow_capabilities.md) for raw tool versus
  workflow capability
- [`workflow_drafts.md`](workflow_drafts.md) for the preferred authoring format
- [`workflow_artifacts.md`](workflow_artifacts.md) for immutable artifacts,
  deployments, and dependency contracts

## Workspace Variant

If the client is iterating with an LLM, prefer a draft workspace:

1. Create a minimal workspace from the selected capability.
2. Fetch the workspace by id when context is needed.
3. Patch it by id and revision.
4. Save an artifact from the workspace after validation is clean.

This avoids resending the whole draft object every turn. The saved artifact is
still immutable and should be deployed through the normal deployment path.

Concrete MCP sequence:

1. `wf.workflow.list_capabilities` with a query such as `echo`.
2. `wf.workflow.call_capability` with a small payload to verify the selected
   capability behaves as expected.
3. `wf.workflow.create_minimal_draft_workspace` with a `request` object that
   contains schemas, `input_map`, and `output_map`.
4. `wf.workflow.list_draft_workspaces` if the client needs to rediscover
   existing workspace ids.
5. `wf.workflow.get_draft_workspace` with `include_draft=true` if the client
   needs to inspect the full current draft.
6. Use focused helpers such as `wf.workflow.set_draft_name` or
   `wf.workflow.set_draft_route`, or call `wf.workflow.patch_draft_workspace`
   with the current `revision` for arbitrary JSON Patch edits.
7. `wf.workflow.validate_draft_workspace` if capabilities changed or you want
   to refresh diagnostics without editing the draft.
8. `wf.workflow.create_artifact_from_workspace` after validation is clean.
9. `wf.workflow.save_deployment`, then `validate_deployment`, then
   `run_deployment`.
10. `wf.workflow.delete_draft_workspace` when the mutable authoring session is no
   longer needed.

`create_artifact_from_workspace` also uses a `request` object:

```json
{
  "request": {
    "workspace_id": "echo_draft",
    "artifact_id": "echo",
    "version": 1,
    "title": "Echo",
    "outcomes": ["completed"],
    "source_bindings": {
      "demo": "demo.personal",
      "wf.std": "wf.std"
    }
  }
}
```
