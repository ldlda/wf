# Draft CLI Vocabulary Design

## Status

Planned. This design generalizes the two remaining capability-specific draft
CLI verbs:

- `wf draft create-from-capability`
- `wf draft add-step-from-capability`

They are replaced at the CLI layer by:

- `wf draft create --capability <qualified_name>`
- `wf draft add-step --capability <qualified_name>`

The long commands should be removed from the CLI, docs, and skills rather than
kept as aliases. The programmatic API/RPC/MCP method names are not renamed in
this slice because they are older, tested surfaces with broader callers than
the CLI benchmark loop.

## Problem

Agents keep trying CLI shapes that match common command vocabulary:

```powershell
wf draft create --capability local.report.extract_report ...
wf draft add-step --capability local.report.render_markdown_report ...
```

The product currently exposes:

```powershell
wf draft create-from-capability ...
wf draft add-step-from-capability ...
```

The long names are precise but hostile to discovery. Skills currently have to
warn agents that `wf draft create --capability` does not exist, which is a sign
that the CLI shape is wrong.

## New CLI Shape

Create a workspace:

```powershell
wf draft create <workspace_id> `
  --capability <qualified_name> `
  --name <draft_name> `
  --title <workspace_title>
```

Add a capability step:

```powershell
wf draft add-step <workspace_id> `
  --revision <n> `
  --step <step_id> `
  --capability <qualified_name> `
  --from-step <prev_step> `
  --from-outcome ok `
  --route ok=__end__ `
  --input input.text=local.text `
  --bind-output result=state.result
```

`--capability` is required for both commands in this slice. Future core step
types can extend `add-step` with `--type condition`, `--type foreach`, or
similar flags, but this slice only renames the current capability-backed
operations.

## Removal Policy

Remove these CLI commands:

- `wf draft create-from-capability`
- `wf draft add-step-from-capability`

Do not keep aliases. These names made sense as implementation descriptions, but
they now actively fight agent behavior. Removing them keeps `wf draft --help`
smaller and prevents skills from teaching two ways to do the same operation.

Keep these programmatic method names for now:

- `create_draft_workspace_from_capability`
- `add_step_from_capability`
- `workflow.draft_workspaces.create_from_capability`
- `workflow.draft_workspaces.add_step_from_capability`
- `wf.workflow.create_draft_workspace_from_capability`
- `wf.workflow.add_step_from_capability`

Those surfaces are outside the immediate CLI vocabulary problem and have older
test/docs coverage. A future transport vocabulary cleanup can rename them if
there is evidence that MCP/RPC callers struggle with the same names.

## Documentation Policy

Live user-facing docs and skills should teach only:

```powershell
wf draft create ... --capability ...
wf draft add-step ... --capability ...
```

Historical docs may keep old command names. Live docs that mention the old CLI
names must either be updated or clearly mark them as historical context.

## Acceptance Criteria

- `wf draft create --capability ...` creates the same workspace as the old
  command.
- `wf draft add-step --capability ...` adds the same capability-backed step as
  the old command.
- `wf draft --help` lists `create` and `add-step`, not the long
  `*-from-capability` CLI commands.
- Skills no longer say “there is no `wf draft create --capability` alias.”
- Existing RPC/MCP tests keep passing without programmatic surface renames.
