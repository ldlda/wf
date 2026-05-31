# Documentation Index

Start here when orienting to the project. Top-level docs are the current
reference unless marked otherwise. Historical scratch notes and completed
implementation plans are kept for context, not as active instructions.

## Current Overview

- [`project_map.md`](project_map.md): package map, entrypoints, examples, tests,
  and verification commands.
- [`current_roadmap.md`](current_roadmap.md): active next-work list after the
  core type-shape cleanup.
- [`wf_core_architecture.md`](wf_core_architecture.md): kernel package
  boundaries, runtime flow, validation flow, and known runtime gaps.
- [`wf_mcp_architecture.md`](wf_mcp_architecture.md): MCP package boundaries,
  dependency rules, reload/proxy behavior, and extraction seams.

## Core Workflow Model

- [`core_state_mapping_and_merge.md`](core_state_mapping_and_merge.md):
  canonical `input` / `output` bindings, interrupt `request` / `resume`
  bindings, state patch rules, reducers, and merge semantics.
- [`structural_refs.md`](structural_refs.md): structural source/capability refs
  and structural graph/local/state path JSON.
- [`schema_validation.md`](schema_validation.md): JSON Schema validation seam
  and current payload validation limits.
- [`workflow_artifacts.md`](workflow_artifacts.md): saved workflow artifacts,
  deployments, dependency compatibility, and interrupt limitations.
- [`durable_run_operations.md`](durable_run_operations.md): `run_deployment`,
  `inspect_run`, bounded trace reads, and `resume_run` behavior.
- [`workflow_drafts.md`](workflow_drafts.md): LLM/human draft authoring format
  above raw workflow plans.

## Authoring

- [`authoring_sketch.md`](authoring_sketch.md): authoring layer direction,
  `NodeSpec`, builder API, and catalog goals.
- [`wf_authoring_control_flow.md`](wf_authoring_control_flow.md): when to use
  `branch`, `handle`, `match`, `when`, and `choose`.

## CLI

- [`wf_cli.md`](wf_cli.md): workflow platform CLI commands, output formats,
  lifecycle flow, and common diagnostics.

## MCP Platform

- [`wf_mcp_operator_manual.md`](wf_mcp_operator_manual.md): start here for
  the MCP-facing workflow lifecycle and tool families.
- [`wf_mcp_end_to_end_runbook.md`](wf_mcp_end_to_end_runbook.md): concrete
  tool-call runbook from capability discovery through deployment, run, resume,
  and cleanup.
- [`wf_mcp_troubleshooting.md`](wf_mcp_troubleshooting.md): diagnostics and
  repair steps for source, deployment, run, and resume failures.
- [`durable_run_operations.md`](durable_run_operations.md): durable run
  records, compact inspection, bounded traces, and resume semantics.
- [`wf_mcp_capability_sources.md`](wf_mcp_capability_sources.md): source model
  for raw capabilities, workflow-ready node specs, admin tools, and docs.
- [`workflow_capabilities.md`](workflow_capabilities.md): distinction between
  raw capabilities, workflow capabilities, wrappers, artifacts, and deployments.
- [`wf_mcp_proxy_reality_and_roadmap.md`](wf_mcp_proxy_reality_and_roadmap.md):
  practical proxy behavior, FastMCP gaps, and local workaround boundaries.

## Protocol Notes

- [`mcp_protocol_proxy_inventory.md`](mcp_protocol_proxy_inventory.md): MCP
  protocol surface inventory for proxy support.
- [`mcp_stateful_runtime_plan.md`](mcp_stateful_runtime_plan.md): stateful MCP
  runtime planning notes.
- FastMCP issue notes:
  [`fastmcp_resource_link_issue_guide.md`](fastmcp_resource_link_issue_guide.md),
  [`fastmcp_resource_link_issue_lda_tries.md`](fastmcp_resource_link_issue_lda_tries.md),
  [`fastmcp_notification_forwarding_issue_lda_tries.md`](fastmcp_notification_forwarding_issue_lda_tries.md).

## Historical Material

- [`historical/scratchpad.md`](historical/scratchpad.md): older graph/model
  design notes.
- [`historical/path_mapping_scratch.md`](historical/path_mapping_scratch.md):
  older path and mapping design thread.
- [`superpowers/plans/`](superpowers/plans/): mostly completed implementation
  plans and execution records. Use them for context, not as the primary source
  of truth.
- [`superpowers/specs/`](superpowers/specs/): design specs produced during
  planning sessions.

## Runtime References

Native subgraphs, concurrent foreach, lineage state, and durable stopped-run
resume now have implemented foundations. Use the current roadmap and ADR/spec
docs as the active references:

- [`current_roadmap.md`](current_roadmap.md): active implementation status and
  next-work list.
- [`adr/0001-scheduler-foundation-before-concurrent-foreach.md`](adr/0001-scheduler-foundation-before-concurrent-foreach.md):
  scheduler foundation decision.
- [`adr/0002-concurrent-foreach-policy-and-barrier-commits.md`](adr/0002-concurrent-foreach-policy-and-barrier-commits.md):
  concurrent foreach policy and barrier commit semantics.
- [`superpowers/specs/2026-05-24-native-subgraphs-design.md`](superpowers/specs/2026-05-24-native-subgraphs-design.md):
  native subgraph design.
- [`superpowers/specs/2026-05-26-durable-workflow-runs-and-resume-design.md`](superpowers/specs/2026-05-26-durable-workflow-runs-and-resume-design.md):
  durable run/checkpoint design.
