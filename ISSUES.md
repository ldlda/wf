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

- [ ] `@lda/workflow-rpc` models only the 12 operations needed by the current
  console explorer. It omits typed access to capabilities, source
  inspect/diagnose, artifact save/delete/create, deployment save/delete, every
  draft operation, and source-registry/admin operations already exposed by the
  Python JSON-RPC server.
- [ ] Python JSON-RPC models and the Effect RPC schemas are maintained by hand
  with no parity check or generated contract. Add an operation-inventory test
  or a code-generation seam so server additions cannot silently remain absent
  from TypeScript.
  - A 2026-07-30 spike confirmed that `fastapi-jsonrpc` already exports a
    complete OpenRPC document for all 70 registered methods. Request payloads
    retain useful Pydantic schemas, so OpenRPC is a viable transport input.
  - Typed-result slices now give `workflow.health`, all artifact, deployment,
    and run operations, every persisted draft-workspace operation, and both the
    capability and source-discovery surfaces named transport-neutral result
    schemas: 53 of 70 methods. The remaining 17 success results still collapse
    to generic objects across stateless draft patch/validate and the
    source-registry/admin operations. Continue introducing operation result DTOs
    before adopting generated TypeScript contracts.
  - The stock `@open-rpc/generator` TypeScript client is not suitable here. It
    exhausted a 4 GB Node heap on the full contract and emitted invalid dotted
    class members plus `any` results for a minimal `workflow.health` contract.
    Keep OpenRPC as an interchange format, but generate a small
    transport-neutral contract manifest rather than adopting its client stack.
