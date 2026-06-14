# Browser Click Workflow Authoring Challenge

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

Start from `skills/`, especially the workflow/CLI skill references, before doing
broad docs or code search. Do not read outside this repository. Do not solve the
challenge with only a standalone Playwright/Python script.

Acceptable product-facing authoring paths:

- create a draft from one capability, patch it with your own RFC 6902 JSON
  Patch, then validate/save/deploy/run it;
- or write your own complete raw JSON/YAML workflow plan and use
  `wf artifact create-from-plan` before deploy/run.

Do not use a pre-existing generated patch or raw-plan answer file. If you find
one, ignore it and author your own workflow definition.

The source capabilities are provided by:

```text
examples/browser_click_workflow/ops.py
```

The run input fixture is:

```text
examples/browser_click_workflow/run-input.json
```

A successful final answer must include:

- the commands you ran,
- the deployment id,
- the run id if one was produced,
- evidence that `before.clicked` is `false`,
- evidence that `after.clicked` is `true`,
- whether any server/browser process remains running.

End your answer with exactly one fenced YAML block using this shape:

```yaml
challenge_report:
  used_product_path: true
  used_helper_script: false
  workflow_file: "path/to/workflow.json-or-yaml-or-patch.json"
  deployment_id: "browser_click_case_study.default"
  run_id: "run_..."
  before_clicked: false
  after_clicked: true
  run_failed: false
  leftover_processes: false
  notes: "short explanation"
```

Set `used_product_path` to true only if the workflow was applied and run through
the `wf` CLI, either in local same-process mode or through `wf-rpc-server`. Set
`used_helper_script` to true if you created a Python script to drive
`WorkflowApi` directly.

If something fails, report the exact command and error instead of hiding it.
