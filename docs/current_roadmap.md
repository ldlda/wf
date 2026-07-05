# Current Roadmap

This is the live, short roadmap. Completed implementation plans and long slice
history live under [`historical/`](historical/). Current architecture references:

- [`wf_api_architecture.md`](wf_api_architecture.md): workflow API, server,
  transport, and source package boundaries.
- [`project_map.md`](project_map.md): package map and entrypoints.
- [`wf_cli.md`](wf_cli.md): current CLI usage.

## Current Product Shape

```text
wf_cli
  -> local WorkflowApi or wf_transport_rpc_http.RpcWorkflowApiClient
  -> wf_server.WorkflowServer
  -> wf_api.WorkflowApi / admin surfaces
  -> wf_core / wf_artifacts / wf_sources_mcp
```

The durable product path is now `wf-rpc-server` plus neutral `wf_config` /
`wf_server` composition. The old `wf-mcp` script remains a legacy/special-purpose
MCP entrypoint and compatibility surface.

## Active Initiative: Workflow Console And Defense Demo

The next product-facing push is a local-first web console and defense demo that
shows the lifecycle without forcing viewers to read raw JSON. It connects to a
loopback `wf-rpc-server` through JSON-RPC, displays lifecycle records and traces,
and runs a prepared `lda.chat` report workflow with a typed human approval
interrupt.

Design contracts:

- [`workflow console, agent demo, and defense presentation`](superpowers/specs/2026-07-01-workflow-console-agent-demo.md)
- [`self-describing interrupt contracts`](superpowers/specs/2026-07-01-self-describing-interrupt-contracts.md)
- [`workflow console lifecycle explorer`](superpowers/specs/2026-07-02-workflow-console-lifecycle-explorer.md)
- [`demo autoplay and replay`](superpowers/specs/2026-07-03-demo-autoplay-replay.md)
- [`defense presentation storyboard`](superpowers/specs/2026-07-04-defense-presentation-storyboard-design.md)

Implementation order:

1. Completed: self-describing interrupt request/resume schemas are carried
   through core execution, persisted run inspection, and resume validation.
2. Completed: deterministic `examples/lda_report_workflow/` case study with
   local document, report, issue-board sources, and typed issue-review
   interrupt.
3. Completed: add a top-level `web/` pnpm workspace with a React/Vite console,
   Hono local server, Effect JSON-RPC boundary, loopback connection flow,
   source inventory, protocol evidence, and production static serving. Design:
   [`workflow console foundation`](superpowers/specs/2026-07-01-workflow-console-foundation-design.md).
   Implementation:
   [`workflow console foundation plan`](historical/superpowers/plans/2026-07-02-workflow-console-foundation.md).
4. Completed: add the generic console lifecycle explorer, exercised first through
   the artifact -> deployment -> run -> trace path, with interactive graph and raw
   RPC evidence. Design:
   [`workflow console lifecycle explorer`](superpowers/specs/2026-07-02-workflow-console-lifecycle-explorer.md).
   Implementation:
   [`workflow console lifecycle explorer plan`](historical/superpowers/plans/2026-07-02-workflow-console-lifecycle-explorer.md).
   Draft workspace inspection reuses the same shell after the first vertical
   path.
5. Completed: the web console can operate the prepared
   `examples/lda_report_workflow/` deployment through run start, typed
   `issue_review` interrupt, resume, trace, and final output inspection.
6. Completed: lifecycle autoplay, typed approval, issue-board output, and replay.
   Design:
   [`demo autoplay and replay`](superpowers/specs/2026-07-03-demo-autoplay-replay.md).
   Implementation:
   [`demo autoplay and replay plan`](historical/superpowers/plans/2026-07-03-demo-autoplay-replay.md).
7. Completed: React presentation mode foundation for the prepared workflow demo.
   Make the report workflow story primary, demote lifecycle evidence to
   supporting panels, and keep the layout usable on a 720p display. Decision:
   [`React presentation mode before Astro`](adr/0003-react-presentation-mode-before-astro.md).
   Design:
   [`React presentation mode`](superpowers/specs/2026-07-03-react-presentation-mode-design.md).
   Implementation:
   [`React presentation mode plan`](historical/superpowers/plans/2026-07-03-react-presentation-mode.md).
8. Completed: constrained demo agent that invokes one prepared recipe macro.
   Live mode is deferred to a future slice; the prepared driver is replay-only
   for now.
   Design:
   [`constrained demo agent`](superpowers/specs/2026-07-03-constrained-demo-agent-design.md).
   Implementation:
   [`constrained demo agent plan`](historical/superpowers/plans/2026-07-03-constrained-demo-agent.md).
9. Completed: implement the approved 12-scene defense storyboard as a no-scroll
   720p compositor. Content and evidence freeze before chat replacement, visual
   polish, or motion tuning. Design:
   [`defense presentation storyboard`](superpowers/specs/2026-07-04-defense-presentation-storyboard-design.md).
   Implementation:
   [`defense storyboard compositor plan`](historical/superpowers/plans/2026-07-04-defense-storyboard-compositor.md).
10. Completed: make the workflow execution handoff the visual center of Scenes
    9 and 10. The canonical replay now drives an interpreted operation surface,
    persistent execution graph, typed interrupt contract, and raw evidence
    drawer. Design:
    [`workflow takes the stage`](historical/superpowers/specs/2026-07-05-workflow-takes-stage-visual-design.md).
    Implementation:
    [`workflow takes the stage plan`](historical/superpowers/plans/2026-07-05-workflow-takes-stage-visual.md).
11. Next: replace whole-stage theme switching with one scalable Editorial
    Canvas and prove the reusable recursive Interactive Figure through Scene 6.
    Design:
    [`defense presentation storyboard`](superpowers/specs/2026-07-04-defense-presentation-storyboard-design.md).
    Implementation:
    [`editorial canvas and Interactive Figure plan`](superpowers/plans/2026-07-05-editorial-canvas-interactive-figure.md).
12. Then: adopt source-owned AI Elements chat primitives against existing
    `AgentMessagePart` / `AgentDriver` contracts.
13. Future: implement Schema Form Surface and synchronized Approval Session.
14. Future: implement Guided Run Beat Gates, presenter companion, Scene 10
    product graph, final scene visuals, evidence assets, and rehearsal timing.
15. Add a static slide/appendix shell only after presentation mode is clear.
    Astro remains an option, not the default next surface.

Boundaries: this is not a production admin panel, generic visual workflow
editor, scheduler, external Google Drive/mail integration, or benchmark evidence
for free-form autonomous planning.

## Priority 1: Product Smoke And Status UX

The platform is usable enough to test as a product. Next work should focus on
clear operator feedback before adding more architecture.

- Completed: `wf status` is a compact read-only target/server status command,
  including durable run counts and the latest run summary when available.
- Completed: a real CLI smoke pass against `wf-rpc-server --config wf.config.json`
  is captured in
  [`2026-06-09 product smoke RPC CLI`](superpowers/research/2026-06-09-product-smoke-rpc-cli.md).
- Completed: `wf artifact inspect` now accepts `--version` as an alias for the
  positional version argument.
- Completed: `wf artifact delete <artifact_id> <version> --confirm` deletes
  unreferenced artifact versions and rejects versions still referenced by
  deployments. Implementation:
  [`wf artifact delete`](historical/superpowers/plans/2026-06-09-wf-artifact-delete.md).
- Completed: `wf draft delete <workspace_id> --confirm` exposes existing draft
  workspace deletion as a safe CLI command. Implementation:
  [`wf draft delete CLI/RPC`](historical/superpowers/plans/2026-06-09-wf-draft-delete-cli-rpc.md).
- Completed: bounded RPC CLI smoke runbook with cleanup commands:
  [`RPC CLI smoke runbook`](runbooks/rpc-cli-smoke.md).
- Completed: automated RPC CLI smoke example:
  [`RPC CLI smoke example`](historical/superpowers/plans/2026-06-09-rpc-cli-smoke-example.md).
- Completed: `cap call` output is safer for humans through compact/text modes
  without changing default JSON semantics. Implementation:
  [`cap call output safety`](historical/superpowers/plans/2026-06-09-cap-call-output-safety.md).
- Completed: raw JSON/YAML workflow plans can be turned into artifacts through
  JSON-RPC and `wf artifact create-from-plan`, allowing agent/evidence harnesses
  to use the product-facing CLI path.
- Completed: the opencode browser-click challenge harness is local-first via
  `wf --config examples/browser_click_workflow/wf.config.json --local`, with
  optional `--start-server` / `--server-url` modes for JSON-RPC-path trials.
- Completed: focused draft edit helpers are exposed through RPC/CLI, and
  `wf deploy create` is accepted as an alias for `wf deploy save`. Docs now
  distinguish draft shape from raw plan shape for agent authoring.
- Completed: `wf draft set-input` and `wf draft set-output` now accept
  `--merge`, preserving existing bindings when agents split map edits across
  multiple revisions.
- Completed: `wf schema` now lists workflow document/component models, emits
  compact JSON outlines for agent discovery, and emits valid self-contained
  JSON Schema with `--verbose`.
- Completed: `wf draft bind --from ... --to ...` composes input/state/output
  schema projection with step binding merge, replacing the prior narrower
  output-to-state helper and reducing manual draft patch repairs in agent
  challenge runs.
- Completed: draft CLI vocabulary now uses `wf draft create --capability` and
  `wf draft add-step --capability`, replacing the longer
  `*-from-capability` commands that agents repeatedly guessed around.
- Completed: `wf draft add-step` inserts one explicit
  capability-backed step with route, input, and output-to-state schema/binding
  wiring in a single revision, reducing brittle JSON Patch authoring for
  multi-step workflows. Accepts `--route OUTCOME=TARGET` for multi-outcome steps.
- Completed: `wf draft branch` and `wf draft handle` provide atomic route
  editing for existing draft steps without rewriting the full routes object.
- Completed: `wf draft compile` returns the compiled raw plan plus required
  capabilities without mutating or saving the draft workspace.
- Completed: draft validation now preserves structured core validation issues
  and adds exact `wf draft bind` repair hints for missing state fields.
- Completed: `wf explain` now covers draft/workflow validation codes such as
  `unknown_edge_destination`, `invalid_source_path`, and `patch_invalid`.
  Implementation plan:
  [`draft explain diagnostics`](historical/superpowers/plans/2026-06-28-explain-draft-diagnostics.md).
- Completed: draft workspaces can persist invalid intermediate route states,
  allowing agents to add missing target steps before final validation/save.
  Implementation:
  [`invalid intermediate draft authoring`](historical/superpowers/plans/2026-06-28-draft-invalid-intermediate-authoring.md).
- Completed: draft workspaces expose focused remove commands for routes, steps,
  and step bindings so agents can recover from bad edits without raw JSON Patch.
  Implementation:
  [`draft remove commands`](historical/superpowers/plans/2026-06-28-draft-remove-commands.md).
- Completed: `wf draft set-workflow-output` and full-stack API/RPC/CLI support
  for editing top-level workflow output bindings. Accepts repeatable `--map`
  and `--merge` flag. Implementation:
  [`set-workflow-output API/RPC/CLI`](historical/superpowers/plans/2026-06-29-set-workflow-output.md).
- Completed: challenge-driven output UX polish makes `set-workflow-output`
  project missing top-level output schema fields from declared `input.*` and
  `state.*` sources, and challenge prompt templates now always include
  `ux_issues_found: []` so debug-profile reports do not fail by omission.
- Completed: `wf draft bind` now reuses existing workflow input/state schema
  fields when binding to step-local inputs, avoiding redundant-schema failures
  found by debug challenge runs. Implementation:
  [`idempotent draft bind inputs`](historical/superpowers/plans/2026-06-29-idempotent-draft-bind-inputs.md).
- Keep status read-only; do not mutate registry, auth, config, or stores.

## Priority 2: Durable Run/Resume Hardening

The v1 durable run and resume path exists, including persisted interrupted runs,
bounded trace reads, dependency revalidation, and process-rebuild resume tests.
Remaining hardening should focus on correctness under real server use.

- Completed: same-process `resume_run` calls are serialized per run id.
  Implementation:
  [`resume run concurrency guard`](historical/superpowers/plans/2026-06-09-resume-run-concurrency-guard.md).
- Completed: store-level locking/transaction expectations are documented for
  current file stores and future transactional stores:
  [`store transaction boundary`](superpowers/specs/2026-06-09-store-transaction-boundary.md).
- Completed: paged `wf run list` exposes compact persisted stopped-run
  summaries without trace or checkpoint state. Implementation:
  [`run list API/RPC/CLI`](historical/superpowers/plans/2026-06-11-run-list-api-rpc-cli.md).
- Preserve existing semantics: broken pinned dependencies return blocked
  readiness and diagnostics; ordinary live tool/source failures are failed runs,
  not implicit pauses.
- Active specs:
  - [`persisted run/resume contract`](superpowers/specs/2026-06-03-persisted-run-resume-contract.md)
  - [`durable workflow runs and resume`](superpowers/specs/2026-05-26-durable-workflow-runs-and-resume-design.md)

## Priority 3: Source/Auth/Config Polish

Source registry, neutral MCP source config, role-specific stores, and local/dev
auth admin are implemented. The next work is polish, not new broad surfaces.

- Keep config bootstrap separate from mutable store-backed source registry state.
- Keep auth payload values write-only; display summaries must show metadata and
  payload keys only.
- Keep role-specific stores filesystem-only until a real SQL/secret-manager slice
  is planned.
- New source families should follow the generic runtime source lifecycle rather
  than being forced through MCP `ConnectionConfig`:
  [`runtime source lifecycle`](superpowers/specs/2026-06-09-runtime-source-lifecycle.md).
- Completed: static config `kind: "python"` sources can load trusted local
  `NodeSpec` registries and expose them through WorkflowServer. Implementation:
  [`static Python sources`](historical/superpowers/plans/2026-06-11-static-python-sources.md).
- Completed: `wf config validate` preflights neutral workflow config files,
  including config-relative path resolution and trusted static Python source
  imports. MCP sources are shape-validated only; live upstream checks remain a
  server/status concern.
- Completed: Python source operator docs and RPC integration coverage now prove
  `ops.py` source config, capability call, draft artifact creation, deployment,
  and workflow run. Runbook:
  [`Python source`](runbooks/python-source.md).
- Completed: static source inventory providers now have an explicit
  `WorkflowSourceProvider.load_sources()` seam in `wf_server`, and Python
  source loading is behind `PythonSourceProvider`.
- Completed: `wf --local --config <workflow-config>` now composes configured
  neutral server sources in-process instead of falling back to built-in static
  sources only. `--local` is process-local server composition, not local-only
  source transports or shared in-memory source sessions.
- Completed: server startup policy moved to `wf_server.cli`; JSON-RPC HTTP
  remains in `wf_transport_rpc_http`:
  [`server CLI and transport boundary`](superpowers/specs/2026-06-10-server-cli-transport-boundary.md).
- Next auth work: typed/discriminated auth records and source-owned auth binders
  (`McpAuthBinder` first) are now completed. Remaining: Google Drive MCP smoke
  through `https://drivemcp.googleapis.com/mcp/v1` (manual/local-only, requires
  Google OAuth client credentials). OAuth refresh-token support and provider
  profiles are now implemented. Production secret manager integration and
  encrypted-at-rest file format remain deferred.
- Completed source auth diagnostics: `wf source diagnose <source_id>` now reports
  transport/auth/catalog state without exposing secret payloads.
- Completed source provider docs: `docs/source_provider_guide.md` now covers
  MCP HTTP, MCP stdio, Python sources, auth refs, OAuth refresh-token setup,
  diagnostics, and the Google Drive MCP caveat.
- Completed platform source policy: documented fixed-id sources such as `wf.std`
  and `wf.source` are platform sources. They resolve by fixed source id, do not
  require self-bindings, and legacy explicit self-bindings such as
  `wf.std=wf.std` are accepted as no-op compatibility. Deployment validation
  still rejects non-self platform-source bindings as stale configuration. Other
  `wf.*` namespaces are described by their own source docs/policies.
- Completed `wf.source.read_resource`: resource refs are inert pass-by-value
  data using `logical_source`; explicit platform helper nodes dereference them
  through runtime/platform context with bounded output.
- Completed source inventory CLI polish: `wf source resources` and
  `wf source prompts` list source-owned resource/prompt names without fetching
  content.
- Active specs:
  - [`workflow config targets and sources`](superpowers/specs/2026-06-03-workflow-config-targets-and-sources.md)
  - [`store-backed source registry`](superpowers/specs/2026-06-03-store-backed-source-registry-design.md)
  - [`runtime source lifecycle`](superpowers/specs/2026-06-09-runtime-source-lifecycle.md)
  - [`server CLI and transport boundary`](superpowers/specs/2026-06-10-server-cli-transport-boundary.md)
  - [`auth/source secrets boundary`](superpowers/specs/2026-06-06-auth-source-secrets-boundary.md)

## Priority 4: MCP Package Split Finish Line

`wf_sources_mcp` now owns upstream MCP source implementation pieces: ids,
registry DTOs, auth/catalog stores, discovery/catalog DTOs, SDK adapter/facade,
runtime pool, schema helpers, tool events, wrappers, and adapter lookup.

Next split work should be selective:

- Avoid new dependencies on the combined `wf_mcp` facade from durable server or
  transport packages.
- Keep `wf_mcp` compatibility shims until callers are retired deliberately.
- Move only pieces with clear package ownership. Do not move proxy/UI/App
  metadata support into workflow transports by accident.
- MCP UI/App metadata remains source/proxy metadata only; do not advertise MCP
  Apps/widget support through durable workflow transports yet.

## Priority 5: Runtime/Core Polish Later

Core runtime foundations for native subgraphs, concurrent foreach, lineage state,
and durable stopped-run resume exist. Return here after product/server UX is
stable.

- Native subgraph polish: optional per-use-site child deployment overrides and
  clearer child trace inspection.
- Concurrent foreach polish: reuse barrier/lineage machinery for future
  fork/gather.
- Protocol-native progress: investigate MCP tasks/progress or WebSocket/SSE only
  after polling `wf run watch` proves insufficient.
- OpenAPI sources: continue from [`openapi capability sources`](openapi_capability_source.md)
  when a real non-MCP source is needed.

## Recently Completed Platform Milestones

- `WorkflowApiSurface` is the protocol-neutral workflow operation contract.
- `wf_transport_rpc_http` exposes local/static and MCP-backed `WorkflowServer`
  over JSON-RPC HTTP.
- `wf` can target local or remote workflow APIs for capability discovery, draft
  authoring, artifact/deployment operations, run, inspect, bounded trace,
  resume, and `cap call`.
- Desired source registry reads, mutations, and explicit apply/reload are exposed
  through JSON-RPC and CLI.
- Neutral `wf_config` can express MCP sources, role-specific filesystem stores,
  and client/server target separation.
- `wf config migrate-mcp` converts legacy broker configs to neutral workflow
  config without mutating the original.
- `McpRuntimePool` is shared for stateful upstream MCP operations and has
  JSON-RPC E2E coverage proving session reuse across workflow runs.
- `wf run watch` provides polling-based progress UX.
- CLI expected errors are compact by default; `wf --verbose ...` preserves raw
  tracebacks for debugging.
- Completed thesis case-study evidence bundle: `examples/report_workflow/`
  provides a deterministic report workflow with Python source, fixture input,
  config, runbook, and tests.
- Completed thesis system-design draft: `docs/thesis/system-design-implementation.md`
  now frames the platform as a formal system design/implementation report backed
  by `docs/thesis/evidence-index.md` and the report-workflow case study.
- Completed supplemental browser-click workflow example with serial multi-node lifecycle evidence.
- Completed: an opencode browser-click challenge harness captures external
  agent trials against the deterministic browser-click workflow example without
  changing product runtime code. The old staged-server modes were replaced by
  per-trial local configs in the generic V2 harness.
- Completed: `skills/`, runbooks, and challenge prompt templates are treated as
  the agent instruction layer. Challenge reports now track when trials rely on
  product code, prior stores, adjacent attempts, or existing example solutions.
- Completed: workflow/CLI agent instructions now form an explicit copyable
  bundle for controlled challenge profiles, use `wf schema` for public shape
  discovery, and avoid implementation/test-file guidance.
- Completed: the generic agent challenge harness now supports data-driven
  manifests, layered prompts, explicit `none|skills|all|debug` profiles,
  one-hour hard ceilings, normalized OpenCode tool/token evidence, policy
  findings, and manual-audited reports. Two data-driven challenges exist:
  browser-click and report-workflow. The central `run_trials.py` runner accepts
  any challenge manifest. The `debug` profile is opt-in and captures
  evidence-backed UX issue reports separately from normal benchmark scoring.
- Completed: report projections generate bounded Markdown and JSON reports for
  every V2 trial and regenerate both after audit without mutating raw evidence.
  Implementation:
  [`report projections`](historical/superpowers/plans/2026-06-23-agent-challenge-report-projections.md).
- Completed: challenge trial collection now supports bounded concurrency through
  `run_trials.py --concurrency` and a Python matrix runner,
  `examples/agent_challenges/run_matrix.py`. The PowerShell matrix helper now
  delegates to the Python runner.
- Completed: shared agent challenge evaluation runbook documents trial
  execution, instruction profiles, manual audit, and the distinction between
  evaluation validity and policy coverage:
  [`agent challenge evaluation`](runbooks/agent-challenge-evaluation.md).
- Completed: challenge matrix operations now have compact OpenCode thread
  titles, policy handling for canonical skill-document reads, and a central
  `summarize_trials.py` command for audited result tables.
- Completed: agent challenge results now record OpenCode session metadata and
  resume commands, so incomplete provider runs can be continued without
  mutating original raw evidence.
- Completed: canonical TOML path strings are the emitted workflow path form.
  Paths now serialize as `"input.text"`, `"state.echoed"`, and `"message"`
  (local). Structural `{"root": "input", "parts": ["text"]}` path objects
  remain accepted and are now advertised in generated schemas as an input form.
- Completed: challenge-driven CLI UX fixes now provide exact available
  deployment binding suggestions, reject bare `--bind-output` state targets
  before RPC with compact guidance, and accept `wf schema --full` as an alias
  for `--verbose`.
- Completed: `wf draft bind` with `--from local.x --to output.y` now lowers
  through state
  atomically (projecting into both state_schema and output_schema), and
  validation repair hints cover undeclared workflow input source paths.
  Implementation plan:
  [`bind repair hints`](historical/superpowers/plans/2026-06-29-draft-bind-repair-hints.md).
- Completed: capability-backed draft creation now auto-binds required inputs
  only; optional inputs are surfaced in wrapper-hint notes for explicit binding.
  Implementation plan:
  [`required-only wrapper inputs`](historical/superpowers/plans/2026-06-29-required-only-wrapper-inputs.md).
- Completed: `wf draft set-input` rejects `local.x` targets before RPC and
  shows the equivalent bare-target mapping.
- Completed: `wf draft add-step --route` errors include declared outcomes and
  direct add/remove repair guidance.
- Completed: repeated idempotent `wf draft bind input/state -> local` behavior
  is covered by regression tests.

Agent evaluation cohort status and policy:

- Treat trials collected while product code, prompts, fixtures, harness logic,
  or workspace isolation were changing as formative evaluation. Preserve them
  as qualitative evidence linking observed agent failures to product/harness
  fixes, but do not pool their timing, token, or success metrics with a frozen
  cohort.
- Completed: the primary longitudinal campaign now has N=3 per cell / 36
  manually audited trials across two challenges, two models, and
  `none|skills|all` profiles. The explicit cohort manifest, aggregate Markdown,
  and SVG/PDF figures live in `docs/thesis/`.
- The 36 trials span repository snapshots and a base-prompt change before the
  third wave. Treat the aggregate as longitudinal product/prompt engineering
  evidence, not as a frozen model comparison or causal profile experiment.
- Keep product code, challenge prompts, supplied skill bundle, model variants,
  timeout, concurrency, fixtures, and enabled tool set fixed if a future
  controlled cohort is collected. Record the product baseline and rendered
  prompt hashes with every result.
- Keep manual audit authoritative for final pass/fail/invalid interpretation.
  Automatic policy findings remain review inputs, not bespoke exceptions or
  final benchmark outcomes.

Planned challenge-driven UX follow-ups:

- Design a separate composite-binding/data-shaping slice for cases such as
  mapping state fields into a structured `report` object. Do not hide this
  behind the existing path binding syntax without a deliberate model.

## Historical References

- [`wf_api extraction roadmap`](historical/superpowers/plans/2026-06-01-wf-api-extraction-roadmap.md)
- [`source registry next slices`](historical/superpowers/plans/2026-06-03-source-registry-next-slices.md)
- [`MCP source connection seam`](historical/superpowers/plans/2026-06-07-mcp-source-connection-seam.md)
- [`MCP runtime RPC session reuse E2E`](historical/superpowers/plans/2026-06-08-mcp-runtime-rpc-session-reuse-e2e.md)
