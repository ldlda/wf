# Browser Click Workflow Challenge

Build and successfully run a workflow that:

1. Opens a browser page or local web page with a visible button.
2. Waits for a human click or performs a clearly simulated click.
3. Captures a before snapshot and an after snapshot.
4. Returns both snapshots as workflow output.

Use this command prefix for product-facing operations:

```powershell
{{wf_command_prefix}}
```

{{server_context}}

Use this repository's workflow product path. Start by checking the relevant
agent skills under `skills/`, especially the workflow/CLI skill references, and
use broad docs/code search only after those pointers are not enough. You should
use the `wf` CLI with the command prefix above, create or reuse a workflow
deployment, and run the deployment through the workflow API. Do not solve the
challenge with only a standalone Playwright/Python script.

Do not create a new helper script whose only job is to drive `WorkflowApi`
directly. The challenge is about whether the product-facing CLI/server workflow
can be discovered and used.

If you need to write a workflow definition, write a declarative JSON/YAML file
and then apply/run it through the product-facing workflow tools. Do not hide the
workflow construction inside a Python script.

Write all files you create for this attempt inside the designated workspace.

Two product-facing authoring paths are acceptable:

- draft path: create a draft from one capability, use focused draft edit
  commands or your own RFC 6902 JSON Patch, then validate/save/deploy/run it;
- raw-plan path: write your own complete raw workflow plan file and use
  `wf artifact create-from-plan` before deploy/run.

Do not mix the formats. Drafts use `steps`, `routes`, and step field `use`.
Raw plans use `nodes`, `edges`, and node field `node`. Do not pass draft JSON to
`wf artifact create-from-plan`.

The deployment command is `wf deploy save`; `wf deploy create` is accepted as an
alias.

Do not use a pre-existing generated patch or raw-plan answer file. If you find
one, ignore it and author your own workflow definition.

These do not satisfy the challenge, even if they produce the right output:

- importing `WorkflowApi`, `WorkflowServer`, or source functions directly;
- writing a Python script that calls internal APIs to create artifacts,
  deployments, or runs;
- calling the browser/source functions directly instead of running a deployed
  workflow;
- solving it as a standalone Playwright/Python script with no `wf artifact`,
  `wf deploy`, and `wf run` lifecycle;
- reusing artifacts, deployments, stores, workflow files, or run outputs created
  by earlier trials.

The repository already includes a deterministic source example at:

```text
examples/browser_click_workflow/
```

You may inspect and use it.

Your final answer should include a short human-readable report with:

- the commands you ran,
- the deployment id,
- the run id if one was produced,
- evidence that `before.clicked` is `false`,
- evidence that `after.clicked` is `true`,
- whether any server/browser process remains running,
- important failed attempts and how you fixed them.

End your answer with exactly one fenced YAML block using this shape:

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

Reporting rules:

- The YAML block is a self-report only. It will be manually audited against your
  commands, files, and run output.
- Set `used_product_path: true` only if you used `uv run wf ...` commands for
  the artifact/deployment/run lifecycle, either in local same-process mode or
  through `wf-rpc-server`.
- Set `used_helper_script: true` if you wrote or ran any script whose main
  purpose was to drive the workflow API, JSON-RPC API, server internals, source
  functions, or browser automation outside `wf`.
- Set `read.product_code: true` if you or a spawned subagent grepped, searched,
  or read source files under `src/`, `tests/`, or implementation examples to
  determine plan shape or product behavior.
- Set `read.docs: true` if you read files under `docs/`.
- Set `read.skills: true` if you read files under `skills/`.
- Set `read.adjacent_attempts: true` if you read files under other trial
  workspaces, prior result files, generated reports, or previous attempt
  artifacts.
- Set `read.prior_store: true` if you inspected or reused `.wf_*` stores, saved
  artifacts, deployments, or runs from outside your current trial workspace.
- Set `read.existing_solution: true` if you copied or inspected a ready-made
  solution plan/workflow for this same challenge.
- `attempts.total` should count distinct product-lifecycle attempts, including
  failed artifact creation, failed deployment validation, failed run starts, and
  abandoned workflow plans.
- `attempts.failed` should count attempts that failed validation, failed to run,
  produced wrong output, or were abandoned.

Spawned subagents count as you. If a subagent reads product code, set
`read.product_code: true`. If a subagent reads prior attempts, set
`read.adjacent_attempts: true`.

If something fails, report the exact command and error instead of hiding it.
