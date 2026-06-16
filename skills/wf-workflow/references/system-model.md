# Workflow System Model

Use this before choosing commands. The platform separates authoring, binding,
and execution so agents can plan with stable records instead of improvising
tool calls.

## Core Objects

- **Source**: an owner of callable capabilities, such as `wf.std`,
  `local.report`, `local.browser_click`, or an MCP connection. Sources may be
  built in, configured Python sources, MCP sources, or future provider types.
- **Capability**: a graph-facing callable contract exposed by a source. It has
  input/output schemas and outcomes. Build workflows from workflow
  capabilities, not raw provider internals.
- **Draft workspace**: mutable, revisioned authoring state. Use it when you are
  building or editing a workflow interactively.
- **Artifact**: immutable saved workflow or wrapper version. Use it when the
  graph should become durable and reusable.
- **Deployment**: mutable environment binding for an artifact version. It maps
  logical sources used by the artifact to concrete sources available now.
- **Run**: durable execution record for a deployment. It stores status, output,
  diagnostics, and a bounded trace history.

## Why Bindings Exist

A workflow artifact should not hard-code every concrete account or source
instance. It records logical source requirements. A deployment decides which
live source satisfies each requirement.

Example:

```text
artifact requires: local.browser_click
deployment binds: local.browser_click -> local.browser_click
```

Platform sources such as `wf.std` are special: they can be omitted or self-bound.
Configured sources usually need explicit deployment bindings.

## Authoring Paths

Use the guided draft path when editing step-by-step:

```bash
wf draft create-from-capability <workspace_id> <capability>
wf draft set-input ...
wf draft set-output ...
wf draft validate <workspace_id>
wf draft save <workspace_id> --artifact <artifact_id> --version 1 --title <title>
```

Use direct plan import only when you already have a complete workflow plan:

```bash
wf artifact create-from-plan workflow.plan.json --artifact <artifact_id> --version 1 --title <title>
```

Draft shape and direct plan shape are different. Drafts use `steps/routes/use`;
direct plans use `nodes/edges/node`.

## Execution And Trace

`wf run start` executes a deployment and returns a run summary. `trace_count` is
the number of stored trace frames for that run, not a success score. In a
three-node serial workflow, a successful run commonly has `trace_count: 3`.

Use trace commands only with explicit bounds:

```bash
wf run trace <run_id> --from 0 --limit 25
```

## Agent Reporting

If a challenge asks whether product code was read, count source files, tests,
and examples as product code. Reading `tests/...` to learn plan shape means
`product_code: true`.

Do not run repository-wide `ruff`, `basedpyright`, or test suites unless the
task asks for repo changes. For workflow operation tasks, validate with `wf`
commands: capability inspection, draft/deployment validation, run status, and
bounded trace reads.
