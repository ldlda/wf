# Opencode Browser Click Challenge Harness

This harness runs agent trials against the browser-click workflow challenge.
It is evidence tooling, not product runtime code.

The deterministic workflow example is:

```text
examples/browser_click_workflow/
```

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
