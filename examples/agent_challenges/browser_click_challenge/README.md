# Opencode Browser Click Challenge Harness

This harness runs agent trials against the browser-click workflow challenge.
It is evidence tooling, not product runtime code.

The harness mechanics (workspace preparation, opencode I/O, report handling,
trial runner) live in the shared modules under
[`examples/agent_challenges/`](../). The browser-click challenge provides
challenge-specific metadata, prompt template, classification, and defaults.

The deterministic workflow example is:

```text
examples/browser_click_workflow/
```

## Default Behavior

By default the harness does not start a `wf-rpc-server`. It prompts agents to
use a per-trial configured local CLI path:

```powershell
uv run wf --config examples/agent_challenges/browser_click_challenge/workspaces/<trial>/wf.config.json --local
```

For each local-mode trial, the harness copies `workspace_template/` into
`workspaces/<model>-trial-<n>/`, generates a config whose Python source path is
relative to that copied config, and injects the config path into the prompt. This
builds the configured workflow server in the CLI process for each command and
uses the copied workspace's durable store. It does not reuse in-memory source
sessions across CLI invocations.

Use `--workspace-template` and `--source-root` to run a same-shape challenge with
a different prompt template or Python source root. Both default to the bundled
browser-click example settings.

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

Variant challenge example:

```powershell
uv run python examples/agent_challenges/browser_click_challenge/run_opencode_trials.py `
  --workspace-template examples/agent_challenges/browser_click_challenge/workspace_template `
  --source-root examples/browser_click_workflow `
  --workspaces-dir examples/agent_challenges/browser_click_challenge/workspaces_alt `
  --results-dir examples/agent_challenges/browser_click_challenge/results_alt
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

It contains the prompt template and local store ignore rules without exposing a
generated draft patch answer file. The harness copies it automatically for
normal local-mode trials and writes `wf.config.json` into the copied workspace.
For manual experiments, copy it under:

```text
examples/agent_challenges/browser_click_challenge/workspaces/
```

`workspaces/` is ignored by Git so trial-created patches, plans, and scratch
files can be graded by hand without polluting the repository. The template's
store directory is also ignored.

## Saving Trial Reports

To save an agent's final answer from a harness result into its trial workspace:

```powershell
uv run python examples/agent_challenges/browser_click_challenge/save_trial_report.py `
  --from-result examples/agent_challenges/browser_click_challenge/results/<trial>.json
```

The script infers the workspace from the result file and only writes
`<trial>/final-report.md`. Add evaluator commentary by editing that file after it
is saved. For manually copied reports, pass an explicit workspace and
`--input-file final-answer.md`.

## Saving Manual Audits

Keep `final-report.md` as captured agent output. If manual review finds that
the agent's YAML self-report was wrong or incomplete, write a sidecar audit:

```powershell
uv run python examples/agent_challenges/browser_click_challenge/save_manual_audit.py `
  --from-result examples/agent_challenges/browser_click_challenge/results/<trial>.json `
  --manual-classification success_code_assisted `
  --set-read product_code=true `
  --set-evidence trace_count=3 `
  --correction "read.product_code: agent reported false, audited true" `
  --notes "Valid product run, but raw plan shape came from product code/tests."
```

The script infers the workspace, run id, deployment id, automatic
classification, read flags, attempts, and notes from the result file. It writes
`<trial>/manual-audit.yaml`. Later benchmark summaries should treat the sidecar
as the human override, not mutate the captured agent report.

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

## Shared Harness Modules

The generic modules in `examples/agent_challenges/` provide reusable harness
logic:

| Module | Purpose |
|--------|---------|
| `workspace.py` | `ChallengeDef`, `TrialConfig`, `TrialWorkspace`, `prepare_trial_workspace`, `write_trial_config`, `starting_trial_index`, `wf_command_prefix_for_config`, `render_prompt`, `server_command` |
| `runner.py` | `ManagedServer`, `start_server`, `run_trial`, `main` — generic trial runner parameterized by `ChallengeDef` and a classification function |
| `opencode_io.py` | `build_opencode_command`, `parse_opencode_output`, `result_text` |
| `reports.py` | `save_report`, `report_from_result`, `save_report_from_result_payload` |
| `classification.py` | `extract_challenge_report` (generic YAML extraction), `_contains_bool_marker` |

The browser-click challenge's `run_opencode_trials.py` and `save_trial_report.py`
are thin wrappers that pass `BROWSER_CLICK_DEF` and the browser-click
classification function to the generic runner. The same pattern can be used to
add new challenges without duplicating the harness.

Committed tests cover harness logic only. They do not invoke opencode.
