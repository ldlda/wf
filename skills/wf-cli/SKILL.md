---
name: wf-cli
description: Use when authoring, validating, deploying, running, or debugging workflows through the repo-local `wf` CLI.
---

# wf CLI

Use the `wf` CLI when an agent needs a shell-friendly workflow lifecycle:

1. Discover capabilities.
2. Create or patch a draft workspace.
3. Validate the draft.
4. Save an artifact.
5. Save and validate a deployment.
6. Run the deployment.
7. Read bounded trace slices only when debugging.

Canonical docs:

- `docs/wf_cli.md`
- `docs/workflow_capabilities.md`
- `docs/workflow_drafts.md`
- `docs/workflow_artifacts.md`
- `docs/durable_run_operations.md`

If the workflow object model is unclear, read
`skills/wf-workflow/references/system-model.md` before choosing commands.

## Core Commands

```bash
wf --config wf.config.json status
wf cap list --format ids
wf cap inspect <capability>
wf cap call <capability> --input '{"field":"value"}'

wf draft create-from-capability <workspace_id> <capability>
# There is currently no `wf draft create --capability` alias.
wf draft inspect <workspace_id> --include-draft
wf draft patch <workspace_id> --revision <n> --input-file patch.json
wf draft set-name <workspace_id> --revision <n> --name <name>
wf draft set-route <workspace_id> --revision <n> --step <step_id> --outcome <outcome> --to <target>
wf draft set-input <workspace_id> --revision <n> --step <step_id> --map input.text=text
wf draft set-input <workspace_id> --revision <n> --step <step_id> --merge --map input.other=other
wf draft set-output <workspace_id> --revision <n> --step <step_id> --map text=state.text
wf draft set-output <workspace_id> --revision <n> --step <step_id> --merge --map other=state.other
wf draft add-state-from-output <workspace_id> --revision <n> --step <step_id> --output <field> --state state.<field>
wf draft bind-output-to-state <workspace_id> --revision <n> --step <step_id> --output <field> --state state.<field>
wf draft add-step-from-capability <workspace_id> --revision <n> --step <step_id> --capability <qualified_name> --from-step <prev> --from-outcome ok --outcome ok --to <next-or-__end__> --input input.text=text --bind-output result=state.result
wf draft validate <workspace_id>
wf draft save <workspace_id> --artifact <artifact_id> --version <n> --title <title>

When `wf draft validate` returns a `repair_hint`, prefer running that focused
command before writing JSON Patch manually. Re-run `wf draft validate` after the
repair.

wf artifact create-from-plan workflow.plan.json --artifact <artifact_id> --version <n> --title <title>
wf deploy save <deployment_id> --artifact <artifact_id> --version <n> --binding <logical>=<concrete>
wf deploy create <deployment_id> --artifact <artifact_id> --version <n>
wf deploy validate <deployment_id>
wf run start <deployment_id> --input-file input.json
wf run trace <run_id> --from 0 --limit 25
```

## Public Discovery Order

Use public CLI surfaces before broader documentation or implementation search:

1. `wf status`
2. `wf cap list --format ids`
3. `wf cap inspect <capability>`
4. `wf schema` to list workflow document/component shapes
5. `wf schema draft`, `wf schema raw`, or `wf schema <Component>`
6. `wf explain <diagnostic-code>` after validation failures

Use `wf schema <name> --verbose` only when the complete JSON Schema is required;
the default compact outline is preferred for agent context.

For `draft set-input` and `draft set-output`, repeated `--map` flags in one
command define the complete replacement map. If you split map edits across
multiple commands, pass `--merge` or the later command replaces the earlier map.

If mapping `LOCAL_SOURCE=state.new_field`, declare the state field first with
`draft add-state-from-output` when the schema should match a capability output
field. Do not hand-copy `$defs` unless the helper cannot express the shape.

Prefer `draft bind-output-to-state` when a step output should write to a new
root state field. It declares the matching state schema and merges the output
binding in one revision-checked edit. Use `draft add-state-from-output` only
when you need the schema declaration without changing bindings.
`bind-output-to-state` requires a capability-backed step with `use`; use JSON
Patch for non-capability/control draft steps.

To add a capability step, prefer `wf draft add-step-from-capability` over raw
JSON Patch when the route, input bindings, and output-to-state bindings are
known. It is explicit and does not guess missing maps.

## Rules

- Use explicit `--config <path>` for examples, challenge workspaces, and
  non-root configs. The default is `wf.config.json` in the current working
  directory.
- Prefer `--input-file` for large JSON.
- Prefer `--format ids` or `--format compact` for discovery.
- Use `wf cap call` as a cheap smoke test before creating a draft.
- Prefer draft workspaces for iterative authoring; use `artifact create-from-plan`
  only when you already have a complete raw JSON/YAML workflow plan.
- Do not request unbounded traces.
- Do not treat wrapper hints as semantic guarantees.
- If validation fails, run `wf explain <code>` or `wf explain --input-file <validation-output.json>`.
- Do not use planning-session specs or implementation plans as user-facing runtime guidance.
- Do not confuse draft shape with raw plan shape: drafts use `steps/routes/use`;
  raw plans use `nodes/edges/node`.
- Use `wf schema` to list workflow document/component shapes.
- Use `wf schema draft`, `wf schema raw`, or `wf schema <Component>` for compact
  JSON guidance before authoring.
- Add `--verbose` only when a complete JSON Schema document is required; it may
  be large.
- Prefer `wf schema` over searching tests or implementation code for draft/raw
  plan shape.
- Treat compact schema output as authoring guidance; use validation commands as
  the source of truth for a concrete document.
- If public commands and supplied skills are insufficient, report the exact
  blocker instead of guessing undocumented fields.
