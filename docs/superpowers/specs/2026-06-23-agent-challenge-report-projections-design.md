# Agent Challenge Report Projections Design

## Status

Approved for implementation planning on 2026-06-23.

## Purpose

Agent challenge trials currently preserve raw result JSON, prompt text, and
normalized metrics, but the central V2 runner does not automatically create a
bounded report for review. Existing report helpers are also not wired into the
V2 run or manual-audit paths.

This slice adds one normalized report model with two generated projections:

- human-readable Markdown in the trial workspace;
- machine-readable JSON beside the raw result.

The raw trial result remains immutable evidence. Manual audit is authoritative
and regenerates both projections without rewriting raw evidence.

## Goals

1. Make every completed, failed, timed-out, or partially parsed trial produce a
   bounded report automatically.
2. Let a reviewer understand a trial without opening a large raw result file.
3. Preserve a machine-readable report suitable for later aggregation.
4. Show ordered commands and tool calls without copying full tool outputs.
5. Keep automatic outcome, policy validity, agent self-report, and manual grade
   distinct.
6. Regenerate both projections after manual audit.

## Non-Goals

- Aggregate model scoring or statistical claims.
- Replacing the immutable raw result JSON.
- Automatically deciding whether reading an example constituted copying a
  ready-made solution when the tool trace is ambiguous.
- Adding the future branching/`foreach` challenge.
- Writing the broader operator/evaluation runbook; that follows this slice.

## Artifact Layout

For a trial slug such as `opencode_deepseek-v4-flash-free-trial-001`:

```text
results/
  opencode_deepseek-v4-flash-free-trial-001.json
  opencode_deepseek-v4-flash-free-trial-001.report.json

workspaces/opencode_deepseek-v4-flash-free-trial-001/
  rendered-prompt.md
  metrics.json
  final-report.md
  manual-audit.yaml              # created after human review
```

The existing result JSON is raw evidence and is never modified by report or
audit commands. The `.report.json` and `final-report.md` files are disposable
projections that can be regenerated.

## Normalized Report Model

Add a versioned Pydantic `TrialReport` DTO. Both output formats must be derived
from the same instance so their meaning cannot drift.

The model contains these sections:

1. **Identity and provenance**
   - report schema version;
   - challenge id;
   - model, variant, profile, and trial index;
   - repository commit and dirty flag;
   - prompt hashes;
   - raw result path and workspace path.
2. **Outcome**
   - automatic task outcome;
   - automatic evaluation validity;
   - duration and return code;
   - assertion or parser failures.
3. **Agent self-report**
   - extracted `challenge_report`, when present;
   - final agent answer, bounded for human rendering.
4. **Command and tool brief**
   - ordinal, tool, status, title;
   - shell command or read/search path when available;
   - failure marker, output character count, and output hash;
   - no full output payload;
   - bounded preview only when useful.
5. **Automatic evidence**
   - token, cost, step, tool-call, and failure counts;
   - observed read categories;
   - product-code escalation;
   - disallowed reads and opaque commands.
6. **Discrepancies**
   - machine-observable conflicts between self-report and policy evidence;
   - for example, `read.product_code=false` while observed reads include source,
     tests, docs, or implementation examples;
   - ambiguous cases remain manual-review pointers rather than automatic facts.
7. **Manual audit**
   - pending when no audit exists;
   - official outcome, auditor, timestamp, corrections, evidence overrides, and
     notes after audit.
8. **Follow-up pointers**
   - concise warnings such as missing report fields, parse failures, opaque
     commands, or required manual checks.

## Markdown Projection

`final-report.md` uses this stable order:

```markdown
# Trial Report
## Outcome
## Agent Self-Report
## Commands And Tool Calls
## Automatic Evidence
## Policy Findings
## Self-Report Discrepancies
## Manual Audit
## Follow-Up Notes
```

The Markdown must remain bounded. It may include complete commands because
commands are audit evidence, but it must not include full tool outputs or raw
JSONL. Long commands and previews receive explicit length limits and retain a
hash/character count in the machine report.

## Machine Projection

`<trial>.report.json` is `TrialReport.model_dump(mode="json")` written with
stable indentation and key ordering. It contains the normalized command/tool
brief and audit information, not full stdout/stderr.

This report is the future aggregation input. Aggregators must not need to parse
Markdown or the agent-authored YAML block.

## Runner Flow

The V2 runner must:

1. execute the trial and retain available stdout/stderr;
2. normalize metrics, policy, parsed text, and challenge report;
3. write the raw result JSON first;
4. build a `TrialReport` from the raw result with audit status `pending`;
5. write `<trial>.report.json` beside the raw result;
6. write `final-report.md` in the workspace;
7. print or return both generated paths.

Report-generation failure must not destroy raw evidence. The runner should
retain the raw result and surface a concise report-generation error to the
caller.

The raw result gains explicit `challenge_id`, `workspace_path`, and
`result_path` fields. Report code must not infer the workspace from an
agent-authored `workflow_file` path.

## Manual Audit Flow

The existing `save_manual_audit.py` remains the review entrypoint.

It must:

1. load the immutable raw result;
2. resolve the workspace from the explicit raw-result field;
3. write `manual-audit.yaml` in the workspace;
4. rebuild `TrialReport` from raw evidence plus the audit;
5. overwrite both generated projections;
6. print the audit, Markdown, and machine-report paths.

The command keeps current correction flags such as `--set-read`,
`--set-evidence`, `--correction`, and `--notes`. A reviewer should be able to
correct a trial in one command without opening the raw result.

## Prompt Clarification

Put the following shared rule in the base challenge prompt so every challenge
uses the same definition:

> Files under `tests/` and `examples/` may contain complete or partial
> solutions. If you inspect them, report `read.product_code: true`; also report
> `read.existing_solution: true` when they provide a ready-made solution, or
> `read.adjacent_attempts: true` when they contain prior trial outputs.

Challenge-specific prompts may explain additional evidence fields but must not
weaken this rule.

## Error Handling

- Missing or malformed challenge reports remain visible as automatic failures
  or follow-up pointers.
- Missing manual audit means `pending`, not failure.
- Unknown tool event types remain counted in automatic evidence.
- Report generation accepts timeout and parse-error results with partial data.
- Invalid manual audit input fails without mutating either generated report.
- Projection writes use temporary files followed by replacement so reviewers do
  not observe half-written reports.

## Testing

Add focused tests proving:

1. one `TrialReport` generates equivalent Markdown and JSON meaning;
2. commands are ordered and full tool output is absent;
3. the V2 runner writes raw result, machine report, and Markdown report;
4. timeout and parse-error trials still generate reports;
5. explicit workspace/result paths are used instead of self-report inference;
6. automatic discrepancies catch observable self-report conflicts;
7. ambiguous existing-solution reads remain manual pointers;
8. manual audit writes YAML and regenerates both projections;
9. failed audit validation leaves prior projections unchanged;
10. shared prompt text includes the `tests/` and `examples/` disclosure rule.

## Follow-Up

After this slice:

1. write the generic challenge operator/evaluation runbook;
2. run repeated browser-click and report-workflow trials;
3. design a third challenge using branching and `foreach` to test graph
   reasoning, routing, iteration isolation, reducers, and recovery from
   validation failures.
