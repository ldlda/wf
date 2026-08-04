# Issues

## Draft authoring parity

- [x] Dedicated draft CLI subcommands cover every draft step kind.
- [x] Draft interrupts preserve request and resume schemas.
- [x] Draft subgraphs preserve workflow references and boundary contracts.

## Draft data-shaping parity

- [x] `wf draft bind` accepts nested node-local targets such as
  `local.report.title`, consistently with canonical `LocalPath`, the runtime
  binding resolver, and `WorkflowBuilder`.
- [x] Capability-step authoring projects workflow input/state schemas for nested
  local targets while preserving their canonical binding paths.
- [x] An atomic API/RPC/CLI helper assembles one structured node input from
  multiple graph paths. Canonical replacement accepts several bindings in one
  revision-checked edit without an intermediate state object or raw JSON Patch.
- [x] Focused draft authoring can add or replace literal node-input bindings
  comparable to `WorkflowBuilder.use(input=[{"target": ..., "value": ...}])`
  through canonical API, RPC, MCP, and CLI surfaces.
- [x] Compatibility step input/output map merges reject canonical lists they
  cannot reproduce exactly, and workflow-output map merges reject requested
  sources with ambiguous fan-out. Canonical replacement remains the supported
  path for ordered fan-out and mixed path/literal bindings.
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
- [x] Capability-step creation accepts `desc`, `retry`, `timeout_seconds`, and
  ordered canonical path/literal inputs through Python, JSON-RPC, MCP, and CLI.
  The focused update operation preserves `use`, routes, and outputs while
  changing selected metadata or atomically replacing the complete canonical
  input list. Changing the capability itself remains an explicit remove/add
  operation. TypeScript JSON-RPC parity remains tracked below.

## Draft revision semantics

- [x] Semantic draft edits consistently check the expected revision before
  reading current draft content or capability metadata. After request-envelope
  validation, stale callers receive the canonical `revision_conflict` result;
  mutation-time revision checking remains the final race-safe guard.

## TypeScript JSON-RPC coverage

- [ ] TypeScript JSON-RPC parity remains incomplete: `@lda/workflow-rpc` models
  only the 12 operations needed by the current console explorer. It omits typed
  access to capabilities, source inspect/diagnose, artifact save/delete/create,
  deployment save/delete, every draft operation, and source-registry/admin
  operations already exposed by the Python JSON-RPC server.
  - All 70 Python methods now have named OpenRPC success schemas, including
    connections, events, and secret-safe auth admin results. No success result
    collapses to a generic object.
  - `contracts/workflow-api.manifest.json` is the checked transport-neutral
    inventory, and `python -m wf_contract_manifest check` is the drift gate.
  - `@lda/workflow-rpc` now generates `WorkflowOperationName`, raw parameter
    and result types, and a 70-operation lookup map from that manifest.
    `pnpm contract:check` detects TypeScript artifact drift.
  - The manifest does not authorize callers: browser authorization, operation
    metadata, and the 12 current Effect RPC implementations remain authored
    boundaries.
  - A fail-closed representative JSON Schema-to-Effect translator now proves
    constrained primitives, objects, arrays, `anyOf`, local references, and
    structurally guarded recursion against synthetic schemas plus
    representative checked manifest components. It rejects unsupported
    `oneOf`, conditional, composition, and unknown-keyword semantics instead of
    weakening them.
  - A test-only parity harness translates the payload and success schemas for
    all 12 authored RPCs: all 24 sides are inside the supported translator
    subset. Eight mismatches are pinned for the current representative result
    fixtures. Run inspect/start/resume use a reduced authored interrupt instead
    of the complete manifest interrupt in both acceptance directions; run trace
    uses a compact trace-page envelope and omits canonical frame identifiers.
  - Runtime decoder migration and broader callable client coverage remain
    incomplete. Migrate the non-run domains first, then resolve the run result
    contract deliberately. Add an input-depth boundary before recursive
    generated decoders become runtime-facing, and keep the browser allowlist
    authored.
- The stock `@open-rpc/generator` TypeScript client is not suitable here. It
  exhausted a 4 GB Node heap on the full contract and emitted invalid dotted
    class members plus `any` results for a minimal `workflow.health` contract.
    Keep OpenRPC as an interchange format, but generate a small
    transport-neutral contract manifest rather than adopting its client stack.
