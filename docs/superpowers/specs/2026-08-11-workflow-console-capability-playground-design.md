# Workflow Console Capability Playground Design

Date: 2026-08-11

Status: Approved design for Workflow Console Slice 4.

Related:

- [Workflow Console draft authoring workbench](2026-08-05-workflow-console-draft-authoring-workbench-design.md)
- [Workflow Console selected-step dataflow](2026-08-09-workflow-console-selected-step-dataflow-design.md)
- [Current roadmap](../../current_roadmap.md)

## Goal

Let an operator inspect and directly call one discovered workflow capability
from the console without first creating a draft, artifact, deployment, or run.
The same slice makes the shared schema form understand self-contained local JSON
Schema references so capabilities such as `wf.source.read_resource` have a real
generated form instead of an unresolved-`$ref` fallback.

A direct capability call is an authoring and runtime smoke test. It is not a
workflow execution: it has no workflow graph, state, routes, persisted run
record, or trace frames.

## Product Contract

The existing Discover route remains the capability catalog. Selecting a
capability opens a detail surface with two views:

- **Contract** shows identity, source, outcomes, schemas, and wrapper hints; and
- **Try capability** shows a generated input form, wrapper deployment context
  when applicable, an explicit call action, and the latest result or failure
  receipt.

The call action must be labelled as immediate execution. A capability may have
external side effects even though the console calls it outside a workflow. The
console never invokes a capability on selection, tab change, reconnect, or form
change, and it never retries a failed call automatically.

Before calling, the operator acknowledges that the selected capability executes
immediately and may have side effects. The acknowledgement resets when the
selected capability or connected target changes. This is an accidental-action
guard, not an authorization mechanism.

The result surface remains visible until the operator calls again, selects a
different capability, or disconnects. It distinguishes:

- input validation errors before any operation is sent;
- a call currently in flight;
- a completed capability outcome and output, including `runtime_error`;
- returned dependency diagnostics; and
- a rejected transport, protocol, or decoding operation.

Every attempted call also records the existing operation evidence. The inline
receipt is the primary feedback for the action; the global evidence ledger is
the detailed protocol history, not the only place an operator can discover a
failure.

## Direct Call Semantics

The console uses the existing `workflow.capabilities.call` operation with:

- `qualified_name`: the selected capability name;
- `payload`: the generated form's JSON object; and
- optional `deployment_id`: explicit deployment context for saved wrappers.

The optional deployment id is an advanced text field for wrapper artifacts in
this slice. Node-spec calls neither display nor send it because the current API
does not apply deployments to direct node-spec calls. Deployment discovery and
selection are not duplicated inside Discover. Empty deployment text is omitted
rather than sent as an empty string.

Direct node-spec calls receive the API's bounded smoke-test runtime context, not
the complete context of a prepared deployment run. A capability that depends on
runtime-only context may therefore return a diagnostic even when its input is
valid. The playground presents this result truthfully and directs operators to
a deployment run when full workflow context is required.

For example, this slice fixes the generated form for
`wf.source.read_resource`, but a direct call still returns `runtime_error`
because the current node-spec call path does not provide platform context.
Reading the resource successfully remains a prepared workflow/deployment-run
operation unless the backend call contract is deliberately expanded later.

The interpreted result preserves:

- qualified capability name;
- source id;
- capability kind;
- deployment id, if any;
- declared outcome;
- structured output or `null`; and
- dependency diagnostics.

Output is presented as a bounded, scrollable structured JSON preview with the
outcome and provenance as readable facts. The existing evidence ledger retains
the request/response exchange and equivalent CLI. This slice does not invent a
second output-schema renderer or truncate the transport contract itself.

A handler exception is currently represented by a successful RPC response with
`outcome: "runtime_error"`, `output: null`, and an error diagnostic. The
playground treats that as a completed call with a failed capability outcome,
not as a transport rejection. Outcomes are otherwise capability-defined; the
UI does not assume that every successful outcome is literally named `ok`.

The RPC method registry marks capability calls as writes because arbitrary
capabilities can mutate external systems. This prevents accidental reuse of
read-only assumptions and keeps the browser allowlist decision explicit.

## Local JSON Schema References

The shared schema normalization module gains a resolver for references within
the same schema document. Callers continue to pass one schema to
`normalizeSchema`; reference lookup, recursion protection, and fallback reasons
stay behind that interface.

This resolver applies only to dynamic capability schemas projected into console
forms. It does not change the generated RPC contract translator: capability
`input_schema` and `output_schema` remain opaque JSON objects at the transport
boundary, while the generated call payload and result use their existing
checked transport schemas.

Supported references are local JSON Pointers beginning with `#/`, including
the common `#/$defs/Name` and legacy `#/definitions/Name` forms. Pointer tokens
decode JSON Pointer escapes (`~0` and `~1`). References may be nested and may
target objects, arrays, scalar fields, or enums.

Resolution is fail-closed:

- unresolved pointers use the existing raw-JSON fallback with an exact reason;
- external URIs and non-pointer anchors remain unsupported;
- recursive reference cycles stop with a bounded cycle error rather than
  recursing indefinitely; and
- structural siblings beside `$ref` that would require JSON Schema intersection
  semantics remain unsupported.

Annotation siblings used by the form, such as `title`, `description`, and
`default`, may decorate the resolved field without changing its structural
contract. The raw-schema disclosure continues to show the original schema,
including `$defs`; resolution is only the form projection.

The acceptance fixture is the actual shape returned by
`wf.source.read_resource`: its `ref` property points to
`#/$defs/SourceResourceRef`, and the form must expose `logical_source`, `uri`,
the defaulted `kind` discriminator, and the optional resource metadata fields.

## Module Design

The modules remain separated by responsibility:

- `schema-form/schema-field` owns local-reference resolution and normalized
  form fields. No route or capability-specific code resolves schemas.
- The existing read-oriented capability client continues to own list and
  inspect operations.
- A focused capability-call client owns `workflow.capabilities.call`, its exact
  payload, and result decoding through the console write executor.
- A capability-playground controller owns selected-capability provenance,
  pending/result/error state, stale-response suppression, and explicit reset
  on target or selection change.
- Discover composes the contract and playground views. It does not call the
  transport directly or duplicate evidence recording.
- A pure evidence-policy module owns redaction and structural bounds. The
  connection reducer applies it to every `evidence_recorded` action before the
  record enters application state, so executor and connection evidence follow
  one retention rule.

The call client interface stays small: one `call` method accepting qualified
name, payload, and optional deployment id. Transport naming, snake-case wire
fields, decoding, and evidence behavior remain inside its implementation.

## TypeScript And Browser Boundary

The generated workflow contract already inventories
`workflow.capabilities.call`; this slice authors it into the Effect RPC group,
method registry, service dispatch, console operation union, and Hono browser
allowlist. Payload and success schemas come from the checked generated contract
through the existing runtime JSON Schema translator. The implementation must
not hand-write a parallel transport schema.

The method registry provides the equivalent CLI:

```text
uv run wf cap call <qualified-name> --input '<json>' [--deployment <id>]
```

Input JSON and identifiers use the existing shell-argument escaping helper.
The interpreter maps snake-case wire fields into the console result model
without discarding diagnostics or nullable output.

The browser allowlist adds only `workflow.capabilities.call`. Source admin,
auth, registry mutation, generic draft replacement, and unrelated operations
remain blocked. Positive allowlist coverage must be paired with representative
negative tests so adding RPC support cannot silently broaden browser access.

`browser-operation-policy` becomes a configured policy module rather than a
single static set. Its interface classifies an operation as allowed, known but
disabled, or unknown. `createApp` receives that policy. The server entrypoint
constructs it from the bound hostname and the explicit environment opt-in; app
tests inject either policy without mutating process-global environment state.
Unknown operations retain the existing `unknown_operation` response, while a
known disabled capability call returns `operation_disabled` with HTTP 403.

The console remains a trusted local-operator tool, not a multi-user authorized
control plane. Direct capability calls are enabled by default only when the web
server binds to a loopback hostname. A non-loopback `WEB_HOST` requires an
explicit `WEB_ENABLE_CAPABILITY_CALLS=1` opt-in before the browser policy admits
this operation. Startup logs and the web runbook must state that this opt-in can
let LAN clients execute side-effecting capabilities against the server's
loopback workflow target. It does not add authentication, TLS, tenant isolation,
or internet-safe deployment guarantees.

When policy blocks a direct call, `/api/rpc` returns an explicit
`operation_disabled` error rather than pretending the generated operation is
unknown. The playground shows that response inline. This slice does not add a
separate policy-discovery endpoint merely to pre-disable the button.

## Errors And Evidence

Form validation prevents calls when required or typed inputs are invalid.
Unsupported schemas retain the existing raw JSON editor rather than guessing a
control. Server validation and capability execution remain authoritative.

When a call fails, the playground keeps the submitted payload visible and shows
the exact mapped console error inline with `role="alert"`. It does not swallow
the rejected promise. A later successful call replaces the failure receipt;
editing alone does not erase it.

Changing the selected capability or connected target invalidates in-flight UI
responses. A late result must not replace the current playground state. If the
call was actually sent, its evidence remains in the global ledger as truthful
history even when the operator changes selection; connection-generation guards
continue to suppress evidence only when the underlying executor is stale.

The current evidence ledger is unbounded, so this slice adds one shared evidence
sanitization policy rather than storing arbitrary capability payloads forever.
The ledger keeps at most 100 recent records. Request and response values are
converted to bounded JSON-safe projections before entering application state,
with maximum depth 8, 100 entries per collection, 4,096 characters per string,
and 32 KiB of serialized content for each request and response projection.
Overflow is represented by explicit truncation markers. Keys matching
`authorization`, `cookie`, `set-cookie`, `token`, `access_token`,
`refresh_token`, `secret`, `password`, `api_key`, or `api-key` are redacted
case-insensitively. The policy applies to existing operations as well as
capability calls and is covered independently from display formatting.

After sanitization, each record includes operation, label, bounded request and
response, duration, target, and equivalent CLI. `EvidenceRecord` gains the
executor's connected target so retained calls remain attributable after a
reconnect. Executors populate it from their configured target, and the initial
health record uses the normalized connected target. The full transport response
is still decoded for the immediate caller; bounding affects retained UI
evidence, not operation semantics.

## Responsive And Accessible Behavior

Desktop keeps catalog results and selected capability detail visible together.
Contract and Try controls use a keyboard-accessible tab or equivalent segmented
interface with stable accessible names.

On narrow screens, the selected detail remains in normal document flow below
the catalog. The generated form and result own internal overflow only for raw
JSON blocks; primary controls do not require horizontal scrolling.

The call button communicates pending state and is disabled while disconnected,
invalid, unacknowledged, or already calling. Status changes use `role="status"`;
failures use `role="alert"`. The result JSON region is labelled and
keyboard-scrollable.

## Out Of Scope

Slice 4 does not include:

- mixed literal/path array or object composition;
- per-array-item source selectors;
- workflow state, routes, run records, traces, interrupts, or resume;
- capability-call presets, saved history, or batch calls;
- automatic retries or polling;
- a deployment catalog embedded in the playground;
- external JSON Schema reference fetching;
- arbitrary JSON Schema composition such as `allOf`; or
- direct graph mutations.

Composite value construction remains Slice 5 and will use this playground to
smoke-test capability behavior without pretending the direct call itself is a
workflow.

## Verification

The implementation must include:

- schema normalization tests for nested local references, escaped pointer
  tokens, annotation siblings, unresolved pointers, external references, and
  cycles;
- a form regression using the real `wf.source.read_resource` schema shape;
- generated-schema parity, RPC group, service dispatch, method registry, and
  equivalent-CLI tests for `workflow.capabilities.call`;
- browser operation allowlist positive coverage plus representative negative
  coverage, loopback-default enablement, and non-loopback opt-in behavior;
- evidence retention, structural bounding, credential redaction, and unchanged
  immediate-result decoding tests;
- capability-call model decoder and client tests for exact payloads, optional
  wrapper deployment omission/inclusion, nullable output, `runtime_error`, and
  diagnostics;
- controller tests for success, validation blocking, operation failure,
  acknowledgement, selection changes, target changes, and stale responses;
- Discover route tests for Contract/Try switching, no automatic invocation,
  explicit call, pending state, result facts, raw output, and inline failure;
- responsive and keyboard-accessibility regressions; and
- a real-server smoke that calls `wf.std.concat` with a literal array and
  separator, then confirms the outcome and output in the console; and
- a real-schema regression that renders `wf.source.read_resource` without an
  unresolved-ref fallback while documenting that its direct call lacks platform
  context.

Focused tests, full web tests, TypeScript typecheck, production build, React
Doctor changed-scope triage, and `git diff --check` are completion gates.
