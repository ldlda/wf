# Report Workflow Example

This example is the deterministic thesis case study. It demonstrates a trusted
Python source that turns project notes into a typed report object without using
remote OAuth, LLM calls, or provider quota.

## Files

- `input.md` — fixture notes.
- `cap-input.json` — capability-call payload generated from the fixture notes.
- `run-input.json` — workflow-run payload containing the fixture notes by value.
- `workflow.plan.json` — three-node raw plan that passes notes by value:
  `read_notes -> extract_report -> render_markdown_report`.
- `ops.py` — Python source exposing `read_notes`, `extract_report`, and
  `render_markdown_report`.
- `wf.config.json` — local server/client config using the `local.report` Python
  source.

## Run

From the repository root:

```powershell
uv run wf config validate examples/report_workflow/wf.config.json
uv run wf-rpc-server --config examples/report_workflow/wf.config.json
```

In another terminal:

```powershell
uv run wf --config examples/report_workflow/wf.config.json status
uv run wf --config examples/report_workflow/wf.config.json cap list --source local.report
uv run wf --config examples/report_workflow/wf.config.json cap call local.report.extract_report --input-file examples/report_workflow/cap-input.json --format compact
```

The full artifact/deployment/run path is covered by
`tests/examples/test_report_workflow_example.py`. To exercise the same
three-node lifecycle manually through the CLI, import the raw plan:

```powershell
uv run wf --config examples/report_workflow/wf.config.json artifact create-from-plan examples/report_workflow/workflow.plan.json --artifact report_case_study --version 1 --title "Report Case Study" --outcome ok --binding local.report=local.report
uv run wf --config examples/report_workflow/wf.config.json deploy save report_case_study.default --artifact report_case_study --version 1 --binding local.report=local.report
uv run wf --config examples/report_workflow/wf.config.json deploy validate report_case_study.default
uv run wf --config examples/report_workflow/wf.config.json run start report_case_study.default --input-file examples/report_workflow/run-input.json --trace-from 0 --trace-limit 5
uv run wf --config examples/report_workflow/wf.config.json run list --limit 5
uv run wf --config examples/report_workflow/wf.config.json run inspect <run_id>
uv run wf --config examples/report_workflow/wf.config.json run trace <run_id> --from 0 --limit 5
```

Draft workspaces are still useful when an agent starts from one capability and
edits toward a complete workflow:

```powershell
uv run wf --config examples/report_workflow/wf.config.json draft create-from-capability report_ws local.report.extract_report --name report_case_study --title "Report Case Study"
uv run wf --config examples/report_workflow/wf.config.json draft set-name report_ws --revision 1 --name report_case_study
uv run wf --config examples/report_workflow/wf.config.json draft set-input report_ws --revision 2 --step call --map input.text=text
uv run wf --config examples/report_workflow/wf.config.json draft set-output report_ws --revision 3 --step call --map title=state.title --map summary=state.summary
uv run wf --config examples/report_workflow/wf.config.json draft validate report_ws
```

`draft create-from-capability` is a best-effort bootstrapper. Focused commands
cover common edits to existing draft fields; structural edits such as adding the
`read_notes` and `render_markdown_report` steps use `draft patch`, or the raw
plan import shown above.

The expected report includes:

- title: `Weekly Project Update`
- three action items
- at least one risk mentioning Google Drive MCP quota
- followups for Markdown rendering and baseline comparison
- rendered Markdown beginning with `# Weekly Project Update`

`read_notes` still accepts a relative `path` for compatibility, but workflow
runs should prefer the by-value `text` input. This keeps challenge workspaces
self-contained and avoids source-directory path resolution surprises.

## Thesis Evidence

The example supports these claims:

- Python sources can expose typed capabilities through the same workflow surface
  as built-in and MCP sources.
- The case-study path is deterministic and does not depend on an LLM or remote
  provider.
- The workflow lifecycle can be exercised through config validation, capability
  inventory, capability calls, artifacts, deployments, runs, inspect, and trace.
