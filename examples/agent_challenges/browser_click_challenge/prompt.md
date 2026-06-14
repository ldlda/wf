# Browser Click Workflow Challenge

Build and successfully run a workflow that:

1. Opens a browser page or local web page with a visible button.
2. Waits for a human click or performs a clearly simulated click.
3. Captures a before snapshot and an after snapshot.
4. Returns both snapshots as workflow output.

A workflow RPC server is already running at:

```text
{{rpc_url}}
```

Use this command prefix for product-facing operations:

```powershell
{{wf_command_prefix}}
```

Use this repository's workflow product path. That means you should use the
`wf` CLI against the provided URL, create or reuse a workflow deployment, and
run the deployment through the workflow API. Do not solve the challenge with
only a standalone Playwright/Python script.

Do not create a new helper script whose only job is to drive `WorkflowApi`
directly. The challenge is about whether the product-facing CLI/server workflow
can be discovered and used.

If you need to write a workflow definition, write a declarative JSON/YAML file
and then apply/run it through the product-facing workflow tools. Do not hide the
workflow construction inside a Python script.

The repository already includes a deterministic source example at:

```text
examples/browser_click_workflow/
```

You may inspect and use it. A successful final answer must include:

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
  workflow_file: "path/to/workflow.json-or-yaml"
  deployment_id: "browser_click_case_study.default"
  run_id: "run_..."
  before_clicked: false
  after_clicked: true
  run_failed: false
  leftover_processes: false
  notes: "short explanation"
```

Set `used_product_path` to true only if the workflow was applied and run through
the `wf` CLI or `wf-rpc-server` path. Set `used_helper_script` to true if you
created a Python script to drive `WorkflowApi` directly.

If something fails, report the exact command and error instead of hiding it.
