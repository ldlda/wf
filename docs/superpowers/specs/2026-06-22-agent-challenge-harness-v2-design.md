# Agent Challenge Harness V2 Design

## Status

Approved design for implementation planning.

## Purpose

The agent challenge harness is an evaluation instrument for the workflow
product's external-agent surface. Version 2 should support multiple challenges,
controlled instruction profiles, long-running trials, normalized tool and token
evidence, and manual audit without embedding challenge-specific executables in
each challenge directory.

The harness does not prove agent effectiveness by itself. It creates repeatable
trial artifacts that make later comparison and manual audit possible.

## Design Goals

1. Keep the challenge task invariant while varying the supplied instruction
   profile.
2. Preserve raw OpenCode output while producing bounded, normalized evidence.
3. Separate task outcome from evaluation validity.
4. Make challenge directories data-only.
5. Keep one profile per invocation so expensive trial matrices are deliberate.
6. Use a one-hour hard ceiling without treating one hour as expected duration.
7. Make prompts, instruction bundles, models, and harness versions auditable.

## Non-Goals

- Preventing an agent from traversing into the repository with a security
  sandbox.
- Treating an agent self-report as authoritative.
- Automatically proving policy compliance for arbitrary shell commands.
- Adding a database, dashboard, or statistical benchmark suite in this slice.
- Making aggregate agent-performance claims before repeated manual-audited
  trials exist.

## Trial Conditions

The harness accepts exactly one `--instruction-profile` per invocation.

### `none`

- Supply the invariant base prompt and challenge prompt.
- Do not copy skills or supporting documentation into the trial workspace.
- Permit challenge files, `wf --help`, `wf schema`, and other public CLI
  discovery surfaces.
- Instruct the agent not to inspect repository skills, docs, examples, tests,
  source, prior trials, or stores.
- If public surfaces are insufficient, the agent should report the blocker and
  finish with a failed task outcome.

### `skills`

- Copy the selected, reorganized workflow/CLI skill bundle and its references
  into the trial workspace under `.agent/skills/`.
- Tell the agent the exact supplied skill path; do not depend on implicit skill
  discovery or Windows symlink support.
- Instruct the agent not to inspect repository examples, tests, source, prior
  trials, or stores.
- If the supplied skills and public CLI surfaces are insufficient, the agent
  should report the blocker instead of reverse-engineering implementation code.

### `all`

- Copy the same reorganized workflow/CLI skill bundle supplied by `skills`.
- Run from the same trial workspace shape, but permit unrestricted repository
  inspection.
- Instruct the agent to start with skills and public docs and inspect examples,
  tests, or source only when genuinely blocked.
- Continue recording and reporting every observed read so use of broader
  context remains measurable.

The repository is not a security boundary. In `none` and `skills`, reading
outside the allowed roots is a contamination signal, not an access-control
failure.

## Prompt Composition

Prompt construction has three explicit layers:

1. **Base prompt:** stable benchmark rules, allowed product path, audit rules,
   final report contract, and general instruction to avoid implementation code
   unless the selected profile allows escalation.
2. **Profile policy fragment:** the `none`, `skills`, or `all` rules above.
3. **Challenge prompt:** task statement, fixtures, success criteria, and
   challenge-specific report fields.

The challenge prompt must remain byte-identical across profiles for a given
challenge version. The harness renders and saves the final prompt in the trial
workspace. Result metadata records paths and SHA-256 hashes for every prompt
layer and the rendered prompt.

## Challenge Package Shape

All executable harness code lives directly under `examples/agent_challenges/`.
Challenge directories become data-only:

```text
examples/agent_challenges/
  run_trials.py
  metrics.py
  save_trial_report.py
  save_manual_audit.py
  base-prompt.md
  browser_click_challenge/
    challenge.yaml
    challenge-prompt.md
    README.md
    workspace_template/
    results/.gitignore
    workspaces/.gitignore
  report_workflow_challenge/
    challenge.yaml
    challenge-prompt.md
    README.md
    workspace_template/
    results/.gitignore
    workspaces/.gitignore
```

Existing challenge-local runners, report wrappers, classifiers, and compatibility
re-exports are removed after migration. They have no production callers and do
not need compatibility treatment.

## Challenge Manifest

`challenge.yaml` defines data needed by the generic harness:

```yaml
version: 1
id: browser_click
prompt: challenge-prompt.md
workspace_template: workspace_template
source:
  id: local.browser_click
  root: ../../browser_click_workflow
  module: ops
  registry: registry
store_root: .wf_browser_click_store
server:
  config: ../../browser_click_workflow/wf.config.json
  default_port: 8772
report:
  required_fields:
    - before_clicked
    - after_clicked
    - leftover_processes
  success_assertions:
    before_clicked: false
    after_clicked: true
    run_failed: false
    leftover_processes: false
```

The generic classifier validates common lifecycle fields and evaluates simple
manifest equality assertions. Challenge-specific success remains provisional
until manual audit.

## Execution Model

The generic runner:

1. Loads a challenge manifest.
2. Selects one instruction profile.
3. Creates a uniquely numbered trial workspace.
4. Copies the workspace template and selected instruction bundle.
5. Writes config with workspace-relative source paths where possible.
6. Renders and saves the prompt layers.
7. Runs OpenCode with the trial workspace as its working directory.
8. Applies a default hard timeout of 3,600 seconds.
9. Preserves raw stdout/stderr and writes normalized evidence.
10. Produces a provisional classification and generated report.

The one-hour timeout is a p99.9-style safety ceiling. Most trials are expected
to complete substantially earlier. Timeout remains a valid terminal outcome.

## OpenCode Event Normalization

OpenCode JSONL currently exposes `step_start`, `step_finish`, `text`, and
`tool_use` events. The extractor preserves the raw stream and creates a bounded
normalized representation.

### Tool Calls

For each tool call, record:

- ordinal and call id;
- tool name;
- status;
- start/end timestamps when available;
- normalized input;
- title and metadata;
- output byte/character count and bounded preview or hash;
- resolved file paths when the tool/input shape permits it;
- whether the call failed.

Do not embed unbounded tool output in `final-report.md`. Raw output remains in
the result JSON for manual inspection.

### Token And Cost Metrics

For every `step_finish`, preserve the observed token object and cost. Produce
aggregate sums for:

- total;
- input;
- output;
- reasoning;
- cache read;
- cache write;
- cost.

The report labels these values as OpenCode-observed metrics because event
semantics may vary by OpenCode/model version. Per-step values remain available
for auditing aggregation behavior.

### Derived Counts

Produce at least:

- assistant step count;
- total tool-call count;
- tool-call counts by tool;
- failed tool-call count;
- shell-command count;
- file-read/search count;
- distinct paths read;
- workflow CLI command count;
- duration and terminal process result.

## Prompt And Instruction Provenance

Each result records:

- challenge id and manifest hash;
- instruction profile;
- base prompt path/hash;
- profile fragment identifier/hash;
- challenge prompt path/hash;
- rendered prompt path/hash;
- copied instruction bundle manifest with relative paths and hashes;
- model and variant;
- OpenCode command/version when available;
- repository commit and dirty-state marker;
- harness version.

This allows comparisons to distinguish model changes from prompt or skill
changes.

## Policy Evidence

Policy assessment is best-effort derived evidence, not proof.

The extractor classifies observed paths into categories such as:

- trial workspace;
- supplied skills;
- public docs;
- examples;
- tests;
- product source;
- adjacent attempts/results;
- prior workflow stores;
- unknown/outside roots.

Structured read/search tool calls can usually be classified from their input
paths. Shell commands are harder: recognized command/path forms may be
classified, while opaque commands are retained as audit evidence and may make
the automatic validity result `unauditable`.

Generated evidence uses two independent dimensions:

```yaml
task_outcome: success
evaluation_validity: contaminated
policy_compliance:
  disallowed_reads:
    - tests/examples/test_browser_click_workflow_example.py
  escalated_to_product_code: true
  opaque_shell_commands: []
```

Allowed values:

- `task_outcome`: `success`, `failed`, `timeout`, `parse_error`, `unknown`;
- `evaluation_validity`: `clean`, `contaminated`, `unauditable`.

The agent's YAML self-report is retained and compared with observed evidence.
Disagreement is reported; observed evidence does not silently rewrite the
self-report.

## Reports And Audit

The harness writes:

- raw result JSON with stdout/stderr;
- normalized `metrics.json`;
- generated `final-report.md`;
- optional `manual-audit.yaml`.

`final-report.md` includes:

1. trial identity and prompt provenance;
2. task outcome and provisional evaluation validity;
3. duration/token/cost summary;
4. tool and command summary;
5. observed reads and policy findings;
6. agent self-report and discrepancies;
7. final agent answer;
8. manual-audit status.

Automatic classification is convenience evidence. `manual-audit.yaml` remains
the authoritative benchmark outcome.

## Skill Reorganization Dependency

The `skills` profile depends on a coherent canonical bundle. Before harness
migration:

1. remove test-file navigation instructions from user-facing skills;
2. separate lifecycle overview from command/reference detail;
3. ensure raw-plan and draft formats are explained without implementation-code
   pointers;
4. make `wf schema`, `wf --help`, validation, inspect, and trace the primary
   discovery surfaces;
5. define an explicit bundle manifest for files copied into trial workspaces.

The harness should consume this bundle manifest rather than hard-code a list of
skill files.

## Error Handling

- Missing/invalid challenge manifests fail before workspace creation.
- Existing trial directories are never overwritten.
- Timeout preserves partial stdout/stderr and normalized events parsed so far.
- Parse errors retain exception type/message and raw output.
- Report-generation failure does not discard the raw trial result.
- Unknown OpenCode event types are preserved in raw output and counted.
- Missing metrics produce explicit `null`/unavailable fields rather than zero.

## Testing

Focused tests should cover:

- manifest loading and validation;
- base/profile/challenge prompt composition and hashes;
- all three instruction profiles and copied bundle contents;
- one-profile-per-invocation CLI behavior;
- default 3,600-second timeout configuration;
- trial cwd and unique workspace numbering;
- JSONL tool/token extraction from realistic fixture events;
- bounded output summaries;
- path categorization and contamination detection;
- opaque shell command handling;
- self-report versus observed-evidence discrepancies;
- task outcome versus evaluation validity;
- browser-click migration with equivalent provisional classification;
- direct execution of central harness commands.

## Implementation Slices

1. **Skill bundle reorganization.** Finalize canonical workflow/CLI skills and
   a copy manifest.
2. **Generic harness v2.** Add manifests, layered prompts, instruction profiles,
   trial cwd, one-hour ceiling, event metrics, policy evidence, and reports.
3. **Challenge migration and expansion.** Convert browser-click to data-only,
   remove local executables, and add the report-workflow challenge.

## Acceptance Criteria

- A browser-click trial can run under each profile using one central command.
- The challenge prompt is identical across profiles.
- Every trial stores prompt/instruction provenance and normalized tool/token
  evidence.
- `none` and `skills` trials report observed prohibited reads as contamination.
- `all` trials permit broader reads while still reporting them.
- Task success and evaluation validity are separate fields.
- A one-hour timeout preserves partial evidence.
- Challenge directories contain no executable runner/report/classifier modules.
- Existing browser-click behavior remains reproducible through the generic
  harness.
