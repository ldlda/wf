# Browser Click Challenge

This challenge tests whether an agent can discover and use the workflow product
path to build and run a browser-click workflow. It is evidence tooling, not
product runtime code.

The deterministic workflow example is:

```text
examples/browser_click_workflow/
```

## Running Trials

Use the central runner from the repository root:

```powershell
uv run python examples/agent_challenges/run_trials.py `
  --challenge examples/agent_challenges/browser_click_challenge/challenge.yaml `
  --instruction-profile skills `
  --model opencode/mimo-v2.5-free `
  --variant high `
  --trials 1 `
  --attach http://127.0.0.1:4096
```

Profiles `none` and `all` are separate invocations:

```powershell
uv run python examples/agent_challenges/run_trials.py `
  --challenge examples/agent_challenges/browser_click_challenge/challenge.yaml `
  --instruction-profile none `
  --model opencode/mimo-v2.5-free `
  --trials 1

uv run python examples/agent_challenges/run_trials.py `
  --challenge examples/agent_challenges/browser_click_challenge/challenge.yaml `
  --instruction-profile all `
  --model opencode/mimo-v2.5-free `
  --trials 1
```

The hard timeout ceiling is 3,600 seconds per trial.

## Default Behavior

By default the harness does not start a `wf-rpc-server`. It prompts agents to
use a per-trial configured local CLI path. Use `--start-server` when the trial
should exercise the JSON-RPC server path.

## Workspace Layout

- `workspace_template/` contains files copied into each isolated trial workspace.
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
  deployment_id: "browser_click_case_study.default"
  run_id: "run_..."
  before_clicked: false
  after_clicked: true
  run_failed: false
  leftover_processes: false
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

The harness parses this report first. If the report is missing, it falls back to
best-effort prose classification.

## Classification

Each trial is classified as one of:

- `success`: output shows workflow usage and before/after clicked states.
- `workflow_script`: output shows a workflow run, but the agent drove it through
  a new helper script instead of the product-facing CLI/server path.
- `workflow_not_used`: output appears to solve the task without `wf`,
  `wf-rpc-server`, deployment, or run evidence.
- `run_failed`: output includes workflow usage but reports a failure.
- `timeout`: the opencode process exceeded the configured timeout.
- `parse_error`: the harness could not read opencode JSON/JSONL output.
- `unknown`: no clear success or failure signal was found.

Automatic success assertions are provisional until manual audit.

## Shared Harness Modules

The generic modules in `examples/agent_challenges/` provide reusable harness
logic. See `workspace.py`, `runner.py`, `opencode_io.py`, `reports.py`,
`classification.py`, and `manifests.py`.

Committed tests cover harness logic only. They do not invoke opencode.
