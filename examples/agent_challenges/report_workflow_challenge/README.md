# Report Workflow Challenge

This challenge tests whether an agent can discover and use the workflow product
path to build and run a three-node report pipeline. It is evidence tooling, not
product runtime code.

For the shared operator workflow, audit commands, and report interpretation, see
[`docs/runbooks/agent-challenge-evaluation.md`](../../../docs/runbooks/agent-challenge-evaluation.md).

The deterministic workflow steps are: `read_notes -> extract_report ->
render_markdown_report`.

## Running Trials

Use the central runner from the repository root:

```powershell
uv run python examples/agent_challenges/run_trials.py `
  --challenge examples/agent_challenges/report_workflow_challenge/challenge.yaml `
  --instruction-profile skills `
  --model opencode/mimo-v2.5-free `
  --trials 1
```

Profiles `none` and `all` are separate invocations:

```powershell
uv run python examples/agent_challenges/run_trials.py `
  --challenge examples/agent_challenges/report_workflow_challenge/challenge.yaml `
  --instruction-profile none `
  --model opencode/mimo-v2.5-free `
  --trials 1

uv run python examples/agent_challenges/run_trials.py `
  --challenge examples/agent_challenges/report_workflow_challenge/challenge.yaml `
  --instruction-profile all `
  --model opencode/mimo-v2.5-free `
  --trials 1
```

The hard timeout ceiling is 3,600 seconds per trial.

## Workspace Layout

- `workspace_template/` holds local store ignore rules (gitignored contents).
- `workspaces/` holds per-trial workspaces (gitignored).
- `results/` holds per-trial result JSON files (gitignored).
- `challenge.yaml` declares the manifest, source, server, and report schema.
- `challenge-prompt.md` contains the task-specific prompt.

## Required Agent Report

The prompt asks the agent to end with one fenced YAML block:

```yaml
challenge_report:
  used_product_path: true
  used_helper_script: false
  workflow_file: "path/to/workflow.json-or-yaml"
  deployment_id: "report_workflow.default"
  run_id: "run_..."
  title_matches: true
  markdown_rendered: true
  run_failed: false
  read:
    skills: true
    docs: true
    product_code: false
    adjacent_attempts: false
    prior_store: false
    existing_solution: false
  attempts:
    total: 1
    failed: 0
  missed_requirements:
    - "none"
  notes: "short explanation"
```

Automatic success assertions are provisional until manual audit.

## Future Design Notes

> Ideas preserved from the original user-authored challenge notes.

The initial challenge is the deterministic three-node report pipeline so results
are auditable. Future expansions could include:

- docs collection -> foreach summarize by person/point
- render markdown -> send to email
- foreach (collect by person -> render markdown -> lookup name -> send to email)
- save somewhere

This exercises many workflow capabilities. To make it easier, the docs could be
very structured: each doc by topic, points by person, or some better system.
