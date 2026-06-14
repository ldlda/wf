# Opencode Browser Click Challenge Harness

This harness runs agent trials against the browser-click workflow challenge.
It is evidence tooling, not product runtime code.

The deterministic workflow example is:

```text
examples/browser_click_workflow/
```

## Default Behavior

By default the harness does not start a `wf-rpc-server`. It prompts agents to
use the configured local CLI path:

```powershell
uv run wf --config examples/browser_click_workflow/wf.config.json --local
```

This builds the configured workflow server in the CLI process for each command
and reuses the configured durable store. It does not reuse in-memory source
sessions across CLI invocations.

Use `--start-server` when the trial should exercise the JSON-RPC server path.
With `--start-server`, the harness starts:

```powershell
uv run wf-rpc-server --config examples/browser_click_workflow/wf.config.json --host 127.0.0.1 --port 8772
```

It waits until `uv run wf --url http://127.0.0.1:8772/rpc status` passes,
injects that URL into the prompt, runs opencode, then stops the server. Use
`--server-url` to target an already-running server.

## One Trial

From the repository root:

```powershell
uv run python examples/agent_challenges/browser_click_challenge/run_opencode_trials.py `
  --model opencode/mimo-v2.5-free `
  --variant high `
  --trials 1
```

Results are written to:

```text
examples/agent_challenges/browser_click_challenge/results/
```

## Manual Authoring Workspace

For manual authoring trials, use:

```text
examples/agent_challenges/browser_click_challenge/workspace_template/
```

It contains a local workflow config and prompt template that point at the
browser-click Python source without exposing a generated draft patch answer
file. Use it as the starting context for an agent trial, or copy it under:

```text
examples/agent_challenges/browser_click_challenge/workspaces/
```

`workspaces/` is ignored by Git so trial-created patches, plans, and scratch
files can be graded by hand without polluting the repository. The template's
store directory is also ignored.

## Optional Opencode Server Attachment

`--attach` is opencode's server attach flag. It connects this non-interactive
run to an already-running opencode server, for example:

```powershell
--attach http://127.0.0.1:4096
```

It is not a direct MCP server URL. If that opencode server is configured with
Playwright MCP tools, then the attached run can use those tools through
opencode. One possible MCP server command for such an opencode setup is:

```json
{
  "command": "npx",
  "args": ["-y", "@playwright/mcp@latest"]
}
```

The baseline challenge does not require Playwright MCP. The score is based on
whether the agent used the workflow product path and produced the expected
workflow output.

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

Committed tests cover harness logic only. They do not invoke opencode.
