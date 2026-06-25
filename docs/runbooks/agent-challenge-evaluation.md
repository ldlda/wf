# Agent Challenge Evaluation Runbook

This runbook is for running and auditing external-agent trials against the
workflow product surface. It covers the shared harness in
`examples/agent_challenges/`, not a specific challenge implementation.

The goal is to measure whether an agent can use public workflow commands and
instructions to build, deploy, and run a workflow. The harness is also a UX
instrument: failed or contaminated trials often point to missing docs, confusing
commands, or product gaps.

## What The Harness Produces

Each trial writes four kinds of evidence:

- Raw result JSON in the challenge `results/` directory. This is immutable raw
  evidence from the runner.
- Machine report JSON beside the raw result, named `*.report.json`. This is the
  bounded projection for analysis.
- Human report Markdown beside the raw result, named `*.report.md`. This is
  useful for reviewing results after workspace cleanup.
- Human report Markdown inside the trial workspace, named `final-report.md`.
  This is the file to read first during manual review.

Manual audits add one more file:

- `manual-audit.yaml` inside the trial workspace. Re-running the audit command
  regenerates the workspace Markdown, result Markdown, and machine report
  projections without mutating the raw result JSON.

## Run One Trial

Run from the repository root. Use `--attach` when an opencode server is already
running.

```powershell
uv run python examples/agent_challenges/run_trials.py `
  --challenge examples/agent_challenges/browser_click_challenge/challenge.yaml `
  --instruction-profile skills `
  --model opencode/deepseek-v4-flash-free `
  --variant high `
  --trials 1 `
  --attach http://127.0.0.1:4096
```

For the report workflow challenge:

```powershell
uv run python examples/agent_challenges/run_trials.py `
  --challenge examples/agent_challenges/report_workflow_challenge/challenge.yaml `
  --instruction-profile skills `
  --model opencode/deepseek-v4-flash-free `
  --variant high `
  --trials 1 `
  --attach http://127.0.0.1:4096
```

The runner prints summary JSON with the trial classification, result path, and
report paths. Read the corresponding `final-report.md` before trusting the
classification.

Use bounded concurrency when collecting larger samples:

```powershell
uv run python examples/agent_challenges/run_trials.py `
  --challenge examples/agent_challenges/report_workflow_challenge/challenge.yaml `
  --instruction-profile skills `
  --model opencode/deepseek-v4-flash-free `
  --variant high `
  --trials 5 `
  --concurrency 2 `
  --attach http://127.0.0.1:4096
```

`--trials 5 --concurrency 2` creates five unique trial workspaces and lets at
most two OpenCode subprocesses run at once.

## Run The Default Matrix

The Python matrix runner expands the bundled challenges, instruction profiles,
and default model set, then schedules them with one global concurrency limit:

```powershell
uv run python examples/agent_challenges/run_matrix.py `
  --trials 5 `
  --concurrency 2 `
  --attach http://127.0.0.1:4096
```

The PowerShell helper is now only a convenience wrapper around the Python
runner:

```powershell
.\examples\agent_challenges\run_matrix.ps1 -Trials 5 -Concurrency 2
```

Avoid treating high-concurrency runs as the same dataset as sequential runs.
Large concurrency can measure provider queueing, OpenCode timeouts, and local
machine contention rather than workflow UX.

## Instruction Profiles

Use profiles to separate product usability from instruction quality:

| Profile | Meaning | Typical Use |
| --- | --- | --- |
| `none` | Base prompt plus challenge prompt only. | Tests discoverability with almost no agent instructions. |
| `skills` | Adds the workflow CLI skill bundle. | Tests the intended public agent instruction layer. |
| `all` | Allows broader docs/code exploration. | Tests whether the repository contains enough information to solve the task, but results are less clean. |

The same model/challenge should be run across profiles when comparing the value
of the instruction layer.

## Suggested Matrix

Start small and grow only after the harness output is stable:

```text
challenge in [browser_click, report_workflow]
profile in [none, skills, all]
model in [deepseek-v4-flash-free, mimo-v2.5-free, nemotron-3-ultra-free]
trials per cell = 3 to 5 while iterating, more for claims
```

Do not treat one successful run as a model-quality result. One run can be useful
as a product UX finding, but not as an aggregate benchmark.

## Manual Review Checklist

Open the trial workspace `final-report.md` and compare it to the raw transcript
when needed.

Check these items:

- Did the agent use the product path: `wf artifact create-from-plan` or draft
  commands, `wf deploy save` or `wf deploy create`, and `wf run start`?
- Did the run actually complete with the required output fields?
- Did the agent write a helper script that directly drives `WorkflowApi` or
  bypasses the CLI/server path?
- Did the agent read implementation code under `src/` or tests under `tests/`?
- Did the agent read a ready-made solution, store internals, adjacent attempt,
  or generated workspace from another trial?
- Did the agent self-report those reads honestly in the YAML block?
- Did opaque shell commands hide important behavior that needs manual review?
- Did the report include a real `run_id`, deployment id, and workflow file path?

## Validity And Coverage

The report separates policy validity from policy coverage.

`evaluation_validity` answers whether the automatic evidence found a rule
violation:

- `clean`: no observed disallowed reads or policy violations.
- `contaminated`: observed disallowed evidence, such as reading a ready-made
  solution or forbidden prior result.
- `unauditable`: reserved for missing or corrupt raw evidence.

`policy_coverage` answers how much of the evidence the automatic pass could
inspect:

- `complete`: automatic policy checks could inspect the recorded tool evidence.
- `partial`: some behavior happened through opaque shell commands. This does not
  automatically invalidate the trial, but it requires manual review.

Manual audit is authoritative for final interpretation. A technically successful
workflow can still be invalid as evaluation evidence if the agent copied from an
existing solution or bypassed the public product path.

## Save A Manual Audit

Use manual audit after reading the report and raw transcript.

```powershell
uv run python examples/agent_challenges/save_manual_audit.py `
  --from-result examples/agent_challenges/browser_click_challenge/results/opencode_deepseek-v4-flash-free-trial-001.json `
  --manual-classification invalid `
  --auditor codex `
  --set-read product_code=true `
  --set-read existing_solution=true `
  --notes "Technical workflow run succeeded, but the trial is invalid because the agent inspected an existing solution."
```

Use `--manual-classification pass` when the run satisfies the challenge and no
disqualifying evidence is found. Use `fail` when the task was not completed.
Use `invalid` when the workflow ran but the evaluation is contaminated,
bypassed, or otherwise not usable as clean benchmark evidence.

## Summarize Audited Results

After manual audits, generate a compact matrix table from the bounded report
projections:

```powershell
uv run python examples/agent_challenges/summarize_trials.py `
  examples/agent_challenges/browser_click_challenge `
  examples/agent_challenges/report_workflow_challenge
```

The table uses `manual_audit.official_outcome` when present, while keeping the
automatic task outcome, policy validity, duration, token count, attempt count,
and read flags visible. Use it as a working operator summary, not as a
statistical claim by itself.

## Common Invalid Patterns

Mark the trial invalid or at least contaminated when any of these happen:

- The agent reads a complete existing solution, such as a fixture workflow plan
  for the same challenge.
- The agent writes a one-off Python runner that calls `WorkflowApi` directly
  instead of using `wf` or the JSON-RPC server path.
- The agent solves the browser/report task outside the workflow runtime.
- The agent uses prior trial artifacts or adjacent generated workspaces.
- The agent reads `.wf_*` store internals under the current or another trial
  workspace in `none` or `skills` profile. Use public commands such as
  `wf draft inspect`, `wf artifact inspect`, `wf deploy validate`, and
  `wf run trace` instead. Store inspection is only acceptable in `all` profile
  and should still be reported.
- The agent reports `product_code: false` after reading `src/`, `tests/`, or
  example implementation files needed to infer the answer.

Reading docs and skills is allowed unless the chosen profile says otherwise.
Reading implementation code is not automatically a product failure, but it must
be reported and usually makes the trial less useful as public-surface evidence.

## What To Claim

Safe claims from small samples:

- A specific model run did or did not complete the challenge.
- A specific UX problem appeared, such as a confusing command name or missing
  schema documentation.
- The instruction layer helped or failed in a specific observed case.

Avoid stronger claims until the matrix has enough audited trials:

- Model A is better than Model B.
- The system generally reduces token usage.
- Agents can reliably author workflows without code reads.
- The benchmark is statistically meaningful.

Use the challenge evidence as product-design feedback first. Treat aggregate
model benchmarking as a later result once trial counts and audit rules are
stable.
