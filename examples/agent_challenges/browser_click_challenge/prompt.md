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
the `wf` CLI, either in local same-process mode or through `wf-rpc-server`. Set
`used_helper_script` to true if you created a Python script to drive
`WorkflowApi` directly.

If something fails, report the exact command and error instead of hiding it.
