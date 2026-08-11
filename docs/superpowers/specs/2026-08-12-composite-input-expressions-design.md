# Composite Input Expressions Design

Date: 2026-08-12

Status: Approved design for Workflow Console authoring Slice 5.

Related:

- [Atomic step input bindings](2026-07-22-atomic-step-input-bindings-design.md)
- [Workflow Console selected-step dataflow](2026-08-09-workflow-console-selected-step-dataflow-design.md)
- [Current roadmap](../../current_roadmap.md)
- [Tracked product gaps](../../../ISSUES.md)

## Goal

Allow one node input value to be assembled recursively from graph paths and
JSON literals. The motivating case is a `wf.std.concat` input whose first item
comes from workflow state and whose second item is a literal. Authors must not
need synthetic state fields, constant nodes, reducers, or ambiguous local paths
such as `items.0` to construct that value.

The model is a data-construction language, not a computation language. Nodes
continue to own concatenation, arithmetic, branching, and other behavior.

## Existing Boundary

Canonical input bindings currently assign one complete graph-path or literal
value to one node-local target:

```json
{"target": "items", "path": "state.items"}
{"target": "separator", "value": " "}
```

Nested object targets work because `LocalPath` traverses mapping properties.
Array elements do not: interpreting `items.0` as an index would make numeric
object keys ambiguous and turn binding order into mutation semantics.

Existing bindings can therefore supply an entire literal array or an entire
path-backed array, but cannot construct one array or object from independently
sourced members.

## Scope

This slice includes:

- a recursive input-expression model in `wf_core`;
- a new additive expression-bearing input binding;
- runtime resolution for literal, path, array, and object expressions;
- validation, persistence, Workflow API, JSON-RPC, MCP, and CLI round trips;
- TypeScript decoding and console authoring support;
- per-item and per-field Literal/Path controls in schema-backed input editors;
- truthful non-empty schemas for `first_item`, `last_item`, and their public
  `wf.std` projections; and
- focused compatibility, limit, error, and end-to-end tests.

This slice excludes:

- arithmetic, interpolation, conditions, transforms, reducers, or capability
  calls inside expressions;
- workflow final-output expressions;
- indexed `LocalPath` semantics;
- direct graph gestures; and
- artifact, deployment, or run workflow completion in the console.

The expression types should be reusable by later workflow-output work, but no
workflow-output behavior changes in this slice.

## Canonical Model

The existing `InputBinding` remains the simple path/value union because it is
also reused by final workflow-output projection. Node-local inputs gain a
step-specific additive union:

```text
InputBinding = InputPathBinding | InputValueBinding
StepInputBinding = InputBinding | InputExpressionBinding
```

The new binding contains a local target and one explicitly tagged expression:

```json
{
  "target": "request",
  "expression": {
    "kind": "object",
    "fields": {
      "items": {
        "kind": "array",
        "items": [
          {"kind": "path", "path": "state.foo"},
          {"kind": "literal", "value": "wowcool"}
        ]
      },
      "separator": {"kind": "literal", "value": " "}
    }
  }
}
```

The recursive union is:

```text
InputExpression =
  LiteralExpression(kind="literal", value=JsonValue)
  | PathExpression(kind="path", path=GraphSourcePath)
  | ArrayExpression(kind="array", items=list[InputExpression])
  | ObjectExpression(kind="object", fields=dict[str, InputExpression])
```

`kind` is a discriminator. Every model forbids extra fields. Literal values use
the existing strict finite-JSON validation. Object keys are JSON strings and
array order is canonical.

Every node-local payload construction boundary uses `StepInputBinding`:

- `NodeUse.input`;
- `SubgraphNode.input`; and
- `InterruptNode.request`.

Workflow final-output fields continue using `InputBinding`, so this slice does
not accidentally authorize expressions at that separate semantic boundary.
Existing path and value bindings remain the preferred representation for
ordinary whole-field assignments. No migration rewrites existing documents.

## Supported Boundary Matrix

| Boundary | Binding type after this slice | Expressions |
| --- | --- | --- |
| Capability/node-use input | `StepInputBinding` | Accepted |
| Subgraph invocation input | `StepInputBinding` | Accepted |
| Interrupt request payload | `StepInputBinding` | Accepted |
| Final workflow output | `InputBinding` | Rejected |
| Compatibility input/output maps | Path/value maps | Rejected as lossy |

All focused API, JSON-RPC, MCP, and CLI operations that create or replace one
of the first three node-local boundaries accept `StepInputBinding`.
Capability add/update and complete step-input replacement therefore accept
expressions. Operations that replace final workflow-output bindings remain
typed as `InputBinding`. OpenRPC and the transport-neutral manifest expose that
distinction; a broad global replacement of `InputBinding` is incorrect.

The persisted draft payload models follow the same boundary. In particular,
`DraftUseStep.input`, `DraftSubgraphPayload.input`, and
`DraftInterruptPayload.request` migrate to `StepInputBinding`, while draft and
compiled workflow final-output fields remain `InputBinding`. This prevents
artifact parsing from rejecting canonical expressions before compilation.

## Resolution Semantics

Resolution is pure and deterministic. One shared core resolver is used by
normal node execution, subgraph invocation, and interrupt request projection:

- literal returns its strict JSON value;
- path reads workflow input, state, or context through the existing safe graph
  path resolver;
- array resolves each item in order; and
- object resolves each named field recursively.

The resolved value is assigned once at the expression binding's local target.
Expressions never mutate an intermediate local payload. Existing target overlap
validation applies across all three binding shapes, so an expression owning
`request` cannot coexist with another binding targeting `request.title`.

A failure identifies the node, binding target, and expression location, for
example `request.items[0]`. Missing graph paths remain typed input-resolution
failures. The final resolved node payload still passes through the capability's
input JSON Schema before invocation.

## Validation

Validation is schema-directed when the target schema is known. The existing
object-only schema-path helper is expanded into one bounded utility shared by
draft projection and console schema projection. It traverses object
`properties`, schema-valued `additionalProperties`, homogeneous array `items`,
tuple `prefixItems`, and bounded local `#/$defs/...` and
`#/definitions/...` references. Unsupported composition keywords fail closed
with a diagnostic identifying the schema location.

Within that supported subset:

- literal values validate against the current expression position;
- path source schemas are checked against the target position when both are
  available and statically comparable;
- array members validate against `items` or the applicable tuple position;
- object members validate against declared properties;
- required properties, `minItems`, and `maxItems` are enforced when declared;
- `$ref` and `$defs` resolve through the existing bounded local-reference
  resolver; and
- unknown fields follow `additionalProperties` rather than an invented UI rule.

Known incompatible source and target schemas reject the mutation. A path whose
source has no authoring-time schema, including dynamic context paths, is accepted
with an explicit deferred-runtime validation status; the final resolved payload
remains authoritative at execution. When both source and target schemas are
known, unions and references are compared only after successful bounded
normalization. If that known-schema comparison uses unsupported constructs or
cannot establish compatibility safely, authoring fails closed rather than
guessing.

Some capabilities intentionally accept empty arrays. `SequenceInput` therefore
remains unchanged. `first_item` and `last_item` instead receive a dedicated
non-empty input model using `Field(min_length=1)`. Their runtime guards remain
defensive. Empty-aware operations continue to use `SequenceInput`.

The service validates expressions before mutation. Runtime validation remains
the final authority for dynamic path values whose concrete data cannot be known
during authoring.

## Safety Limits

Expression parsing and resolution enforce explicit limits aligned with the
existing bounded JSON contracts. A dedicated root parser walks the submitted
tree before Pydantic union validation and is reused before runtime resolution:

- maximum recursive container depth: 64;
- maximum total expression nodes: 1,024;
- nested containers inside literal JSON values count toward the same depth and
  container budget;
- existing JSON response/request byte limits remain unchanged; and
- cyclic model references may describe data recursively, but submitted
  expression documents are finite JSON trees.

Limit errors are validation errors, not recursion crashes or partially applied
draft mutations.

## API And Transport Behavior

Focused step-input replacement changes from `InputBinding` to
`StepInputBinding` and remains the mutation seam. No second composite
mutation operation is added. The new binding must round-trip through:

- `WorkflowApiSurface` and its service implementation;
- JSON-RPC request models, OpenRPC, and the contract manifest;
- the remote Python client;
- the legacy MCP workflow surface;
- CLI bindings files; and
- the generated TypeScript contract plus authored browser decoder.

Canonical operation behavior is explicit:

- complete node-local replacement preserves and accepts expressions;
- focused node-local creation/update accepts expressions when it accepts a
  complete canonical binding list;
- compatibility map merge/upsert rejects expressions it cannot represent; and
- legacy draft normalization preserves canonical expression records after
  normalizing deprecated fields, but deprecated maps cannot create them.

CLI inline flags remain optimized for simple path/value bindings. Composite
expressions use the canonical bindings JSON file initially; a compact inline
expression syntax is explicitly out of scope.

Lossy compatibility map helpers must reject expression-bearing canonical lists
they cannot reproduce exactly. They must not flatten expressions or silently
discard nested source information.

## Console Interaction

The selected-step Inputs inspector keeps the current outer binding-row model
and adds a recursive editor state:

```text
ExpressionEditorState =
  LiteralState(value, touched)
  | PathState(path, touched)
  | ArrayState(items: ExpressionEditorState[])
  | ObjectState(fields: ordered entries of name + ExpressionEditorState)
```

Projection from canonical bindings to editor state and serialization back are
pure functions with round-trip tests. An expression the current editor cannot
represent remains visible as an unsupported canonical record and blocks
replacement; it is never replaced with an empty literal or raw-JSON fallback.

Core models and transports round-trip expressions for capability, subgraph, and
interrupt-request inputs in this slice. The first console editor is deliberately
narrower: it appears in the selected capability step's Inputs inspector. Later
typed subgraph and interrupt editors reuse the same projection model in Slice 8.
Until then, the console preserves their canonical expressions without offering
a lossy specialized editor.

For a schema field, the author chooses one of:

- Path;
- Literal; or
- Construct, when the field schema is an array or object.

Constructed arrays show ordered items. Each item independently chooses Path,
Literal, or another Construct when its schema permits nesting. Authors can add,
remove, and reorder items. Constructed objects show schema properties; each
property independently selects its source. Required fields are visibly marked.
When `additionalProperties` is a schema, authors may add and remove named fields
using that schema. Boolean `additionalProperties: true` uses a bounded generic
JSON literal/path editor; `false` forbids new names.

The form emits one expression binding for the composite field, never synthetic
targets such as `items.0`. Existing simple rows remain unchanged. Unsupported
schema composition fails closed with a readable explanation and preserves raw
canonical data rather than coercing it into a weaker editor.

For a non-empty schema, removing the final item leaves the form invalid and
explains the cardinality requirement. For schemas that permit empty arrays,
submitting an empty constructed array remains valid.

## Compatibility Audit

Every branch over node-local `StepInputBinding` must become exhaustive. Code
that intentionally handles only simple `InputBinding`, especially workflow
final-output projection, must remain narrow and reject expression records. The
audit includes:

- core validation and runtime node/subgraph resolution;
- draft schema projection and mutation helpers;
- compatibility map merge/rebuild code;
- artifact parsing and persistence;
- API/RPC/MCP request and response models;
- CLI parsing, rendering, and explain guidance;
- contract generation and TypeScript decoders; and
- console projections, copy helpers, forms, and graph summaries.

Unknown binding variants fail closed. Existing persisted path/value bindings
must retain byte-equivalent canonical JSON after parse and serialization where
the current serializers already guarantee it.

Expression strictness applies after existing legacy field normalization.
Expressions are accepted only through canonical binding lists; deprecated
`input_map`, `input_values`, and equivalent compatibility payloads cannot
encode or synthesize them.

## Testing

Tests proceed from the core outward:

1. model parsing, strict JSON, discriminators, limits, and serialization;
2. recursive runtime resolution for arrays, objects, and nested combinations;
3. exact failure paths for missing sources and malformed expressions;
4. target-overlap and schema compatibility validation;
5. revision-checked draft replacement and persistence round trips;
6. API, RPC, client, MCP, CLI, OpenRPC, manifest, and TypeScript parity;
7. console projection and generated-form interaction tests;
8. `first_item` versus `first_item_maybe` cardinality behavior; and
9. an end-to-end `wf.std.concat` draft with a state-backed first item, literal
   second item, and literal separator.

Regression coverage proves old path/value workflows execute unchanged and
compatibility helpers reject, rather than corrupt, expression bindings.

## Success Criteria

The slice is complete when an author can configure and persist this input from
the console and canonical APIs:

```text
items = [path(state.foo), literal("wowcool")]
separator = literal(" ")
```

The resulting `wf.std.concat` node receives the correctly ordered array, while
all existing simple bindings remain valid. No synthetic state, constants,
reducers, indexed local paths, or raw draft patches are required.
