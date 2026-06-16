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
wf draft set-output <workspace_id> --revision <n> --step <step_id> --map text=state.text
wf draft validate <workspace_id>
wf draft save <workspace_id> --artifact <artifact_id> --version <n> --title <title>

wf artifact create-from-plan workflow.plan.json --artifact <artifact_id> --version <n> --title <title>
wf deploy save <deployment_id> --artifact <artifact_id> --version <n> --binding <logical>=<concrete>
wf deploy create <deployment_id> --artifact <artifact_id> --version <n>
wf deploy validate <deployment_id>
wf run start <deployment_id> --input-file input.json
wf run trace <run_id> --from 0 --limit 25
```

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
- `wf schema` is currently only an empty command group; do not rely on it for
  workflow plan shape until subcommands exist.
