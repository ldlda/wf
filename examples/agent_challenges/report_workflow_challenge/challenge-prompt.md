# Report Workflow Challenge

Build and successfully run a workflow that processes structured notes into a
rendered markdown report.

The workflow must execute these three steps in sequence:

1. `read_notes` -- accept structured input notes by value
2. `extract_report` -- extract report content from the notes
3. `render_markdown_report` -- render the extracted content as a markdown report

Prefer passing the notes as workflow input field `text`; do not rely on a file
path into the source example directory. The challenge workspace is isolated, and
the workflow definition should be self-contained.

The writable trial workspace includes safe fixture input files:

- `input.md` -- structured notes for the report
- `run-input.json` -- run input containing the same notes by value in field
  `text`

You may use `run-input.json` with `wf run start --input-file`. Do not copy files
into `examples/report_workflow/`, and do not inspect source implementation files
to learn path behavior. Use `wf cap inspect` for node contracts.

## Workflow Authoring Paths

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

## Disallowed Approaches

These do not satisfy the challenge, even if they produce the right output:

- importing `WorkflowApi`, `WorkflowServer`, or source functions directly;
- writing a Python script that calls internal APIs to create artifacts,
  deployments, or runs;
- calling the source functions directly instead of running a deployed workflow;
- solving it as a standalone script with no `wf artifact`, `wf deploy`, and
  `wf run` lifecycle;
- reusing artifacts, deployments, stores, workflow files, or run outputs created
  by earlier trials.

## Evidence Requirements

Your final answer should include a short human-readable report with:

- the commands you ran,
- the deployment id,
- the run id if one was produced,
- evidence that the report title equals `Weekly Project Update`,
- evidence that the rendered markdown begins with `# Weekly Project Update`,
- important failed attempts and how you fixed them.

## Required YAML Report

End your answer with exactly one fenced YAML block using this shape:

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

Reporting rules:

- The YAML block is a self-report only. It will be manually audited against your
  commands, files, and run output.
- Set `used_product_path: true` only if you used `uv run wf ...` commands for
  the artifact/deployment/run lifecycle, either in local same-process mode or
  through `wf-rpc-server`.
- Set `used_helper_script: true` if you wrote or ran any script whose main
  purpose was to drive the workflow API, JSON-RPC API, server internals, or
  source functions outside `wf`.
- Set `title_matches: true` if the rendered report title equals
  `Weekly Project Update`.
- Set `markdown_rendered: true` if the output is valid markdown beginning with
  `# Weekly Project Update`.
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
