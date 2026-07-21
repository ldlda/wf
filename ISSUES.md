# Issues

## Draft authoring parity

- [x] Dedicated draft CLI subcommands cover every draft step kind.
- [x] Draft interrupts preserve request and resume schemas.
- [x] Draft subgraphs preserve workflow references and boundary contracts.

## Draft data-shaping parity

- [ ] `wf draft bind` rejects nested node-local targets such as
  `local.report.title`, even though canonical `LocalPath`, the runtime binding
  resolver, and `WorkflowBuilder` support nested local paths.
- [ ] Capability-step authoring persists nested input targets but silently skips
  workflow input/state schema projection when a target has more than one path
  segment.
- [ ] No atomic API/RPC/CLI helper assembles one structured node input from
  multiple graph paths. The current focused path requires several
  revision-checked edits and an intermediate state object, or a raw map/patch.
- [ ] Focused draft authoring cannot add or update literal node-input bindings
  comparable to `WorkflowBuilder.use(input=[{"target": ..., "value": ...}])`
  without raw JSON Patch.
- [ ] Focused step input/output maps collapse valid canonical fan-out bindings.
  A source-to-target dictionary cannot represent one graph source feeding two
  local inputs, or one local output feeding two state targets; a later merge can
  therefore rewrite a valid binding list into a lossy map.
- [ ] Focused workflow-output authoring cannot add or update literal output
  bindings even though `WorkflowDraft.output` accepts canonical value bindings.
- [ ] Workflow output schema projection skips nested sources such as
  `state.report.title`, leaving callers to patch the output schema manually even
  when the nested source schema is already declared.
- [ ] CLI help and agent instructions describe step-input targets as bare local
  fields and do not document the nested composition behavior already supported
  by the canonical runtime model.

## Draft workspace lifecycle parity

- [ ] No capability-free draft workspace creation is exposed through the
  transport-facing API, JSON-RPC, or CLI. Control-first, interrupt-first, and
  subgraph-first workflows must bootstrap from an unrelated capability or be
  created through a lower-level raw document path.
- [ ] No focused operation changes the draft entry point. `WorkflowBuilder`
  exposes `set_entry_point`, while workspace callers must patch `/start`
  directly after replacing the bootstrap step.
- [ ] No focused operation declares workflow outcomes. `wf draft add end
  --outcome error` can add the terminal node, but core validation rejects it
  until the caller separately patches `/outcomes`.
- [ ] No focused operation updates workflow input/state/output schemas or state
  reducer declarations after workspace creation. These modeled workflow
  contracts currently require RFC 6902 edits.
- [ ] The dedicated capability-step CLI cannot set `desc`, `retry`,
  `timeout_seconds`, or literal inputs at creation, and there is no focused
  update-step operation. The generic RPC step payload can represent these
  fields, but CLI repair still requires remove/re-add or raw patching.

## Draft revision semantics

- [ ] Semantic draft edits do not consistently check the expected revision
  before reading and validating current content. `add_step` now gates preflight
  on the revision, but bind, capability-add, branch/handle, and remove helpers
  can report a current-content error to a stale caller instead of the canonical
  `revision_conflict` result.

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
