# lda.chat Report Workflow

This example is a deterministic case study for the Workflow Console and defense
demo. It uses local fixture documents, trusted Python sources, a typed
`issue_review` interrupt, and a local JSON-backed issue board.

It does not call Google Drive, email, GitHub, or an LLM.

## Sources

- `local.lda_docs`: lists and reads deterministic project documents.
- `local.lda_report`: analyses documents, builds the readiness report, creates
  proposed issue drafts, and finalises the report.
- `local.issue_board`: writes selected issues to a local JSON file.

## Workflow Definition

`workflow.plan.json` is generated from `build_workflow.py`. After changing the
graph, regenerate and review the raw plan:

```powershell
uv run python examples/lda_report_workflow/build_workflow.py
```

## Product Path

From the repository root:

```powershell
uv run wf --config examples/lda_report_workflow/wf.config.json config validate
uv run wf --config examples/lda_report_workflow/wf.config.json --local cap list --source local.lda_report
uv run wf --config examples/lda_report_workflow/wf.config.json --local artifact create-from-plan examples/lda_report_workflow/workflow.plan.json --artifact lda_report_case_study --version 1 --title "lda.chat Report Case Study" --outcome completed --outcome cancelled --binding local.lda_docs=local.lda_docs --binding local.lda_report=local.lda_report --binding local.issue_board=local.issue_board
uv run wf --config examples/lda_report_workflow/wf.config.json --local deploy save lda_report_case_study.default --artifact lda_report_case_study --version 1 --binding local.lda_docs=local.lda_docs --binding local.lda_report=local.lda_report --binding local.issue_board=local.issue_board
uv run wf --config examples/lda_report_workflow/wf.config.json --local run start lda_report_case_study.default --input-file examples/lda_report_workflow/run-input.json
```

The run stops at an `issue_review` interrupt. Inspect it:

```powershell
uv run wf --config examples/lda_report_workflow/wf.config.json --local run inspect <run_id>
```

Resume with selected issues:

Copy one or more actual issue ids from the interrupt payload and replace the
placeholder below.

```powershell
uv run wf --config examples/lda_report_workflow/wf.config.json --local run resume <run_id> --payload '{"approved":true,"selected_issue_ids":["<issue_id_from_interrupt>"],"comment":"Create selected issues."}'
```

## Cleanup

The example writes `.wf_lda_report_store/` and `issue-board.json`, both ignored
by git.
