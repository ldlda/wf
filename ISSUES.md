# Issues

## Draft authoring parity

- [x] Dedicated draft CLI subcommands cover every draft step kind.
- [x] Draft interrupts preserve request and resume schemas.
- [x] Draft subgraphs preserve workflow references and boundary contracts.

## Draft data-shaping parity

- [x] `wf draft bind` rejects nested node-local targets such as
  `local.report.title`, even though canonical `LocalPath`, the runtime binding
  resolver, and `WorkflowBuilder` support nested local paths.
- [x] Capability-step authoring persists nested input targets but silently skips
  workflow input/state schema projection when a target has more than one path
  segment.
- [x] An atomic API/RPC/CLI helper assembles one structured node input from
  multiple graph paths. Canonical replacement accepts several bindings in one
  revision-checked edit without an intermediate state object or raw JSON Patch.
- [x] Focused draft authoring can add or replace literal node-input bindings
  comparable to `WorkflowBuilder.use(input=[{"target": ..., "value": ...}])`
  through canonical API, RPC, MCP, and CLI surfaces.
- [ ] Compatibility step input/output maps can still collapse valid canonical
  fan-out bindings. Canonical input and output replacement preserve ordered
  fan-out, but later compatibility-map merges remain inherently lossy.
- [x] Focused workflow-output authoring supports literal output bindings through
  canonical Python, JSON-RPC, MCP, and CLI replacement surfaces.
- [x] Workflow-output replacement projects nested `input.*` and `state.*`
  source schemas, including local references, into missing nested public output
  targets without requiring raw schema patches.
- [x] CLI help and agent instructions describe step-input targets as bare local
  fields and do not document the nested composition behavior already supported
  by the canonical runtime model.

## Draft workspace lifecycle parity

- [x] Capability-free draft workspace creation is exposed through the
  transport-facing API, JSON-RPC, and CLI for control-first, interrupt-first,
  end-first, and subgraph-first authoring.
- [x] A focused revision-checked operation changes the draft entry point
  without patching `/start` directly.
- [x] A focused contract operation replaces the complete declared workflow
  outcomes list.
- [x] A focused contract operation replaces workflow input/state/output
  schemas, preserving reducer metadata carried by the supplied state schema.
- [ ] The dedicated capability-step CLI cannot set `desc`, `retry`,
  `timeout_seconds`, or literal inputs at creation, and there is no focused
  update-step operation. The generic RPC step payload can represent these
  fields, but CLI repair still requires remove/re-add or raw patching.

## Draft revision semantics

- [x] Semantic draft edits consistently check the expected revision before
  reading current draft content or capability metadata. After request-envelope
  validation, stale callers receive the canonical `revision_conflict` result;
  mutation-time revision checking remains the final race-safe guard.

## TypeScript JSON-RPC coverage

- [ ] `@lda/workflow-rpc` models only the 12 operations needed by the current
  console explorer. It omits typed access to capabilities, source
  inspect/diagnose, artifact save/delete/create, deployment save/delete, every
  draft operation, and source-registry/admin operations already exposed by the
  Python JSON-RPC server.
- [ ] Python JSON-RPC models and the Effect RPC schemas are maintained by hand
  with no parity check or generated contract. Add an operation-inventory test
  or a code-generation seam so server additions cannot silently remain absent
  from TypeScript.
