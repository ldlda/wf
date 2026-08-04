# Workflow Contract Manifest Design

## Status

Approved design for the first TypeScript parity slice after all 70 Python
JSON-RPC methods gained named success-result schemas.

## Problem

The Python JSON-RPC server exposes 70 methods through a complete OpenRPC
document. The Effect RPC package currently models 12 of those methods by hand.
Operation names are also repeated across `rpcs.ts`, `service.ts`, the method
registry, and console contracts. A Python method can therefore be added or
changed without any deterministic signal that TypeScript is stale.

The stock OpenRPC TypeScript generator is not suitable for this repository. A
local spike exhausted a 4 GB Node heap and produced invalid dotted members and
`any` results. Directly replacing the working Effect schemas would also combine
three separate risks: OpenRPC normalization, JSON Schema translation, and
runtime client migration.

## Decision

Introduce a checked-in, transport-neutral workflow contract manifest before
generating TypeScript.

The first slice will:

1. generate OpenRPC from the real composed Python server;
2. normalize it into a smaller deterministic manifest;
3. validate structural and reference invariants;
4. check in the resulting artifact; and
5. fail tests when the generated contract and checked-in artifact drift.

It will not modify the TypeScript runtime, generate Effect schemas, add an HTTP
endpoint, or expose more browser operations.

## Alternatives Considered

### Check In Raw OpenRPC

Rejected. Raw OpenRPC contains framework-owned document metadata and generated
schema titles that create noise without improving the wire contract. It also
forces every consumer to understand the full OpenRPC document shape.

### Generate Effect RPC Directly

Deferred. Pydantic JSON Schema and Effect Schema differ around optional versus
nullable values, unions, maps, excess properties, and arbitrary JSON. A direct
migration would make extraction failures difficult to distinguish from runtime
schema failures.

### Generate TypeScript Types But Handwrite Effect Schemas

Rejected as the target architecture. It would preserve two TypeScript contract
definitions for every operation while leaving runtime validation manual.

## Package Boundary

Create `src/wf_contract_manifest/` as a focused tooling package. It depends on
the composed server and JSON-RPC transport to obtain OpenRPC, but it is not part
of either package's runtime behavior.

The package will contain these responsibilities:

- `model.py`: manifest structures and `ManifestError`;
- `normalize.py`: pure `manifest_from_openrpc(document)` transformation;
- `generate.py`: compose a temporary local workflow server and obtain OpenRPC;
- `io.py`: deterministic serialization, writing, and checked-file comparison;
- `__main__.py`: `python -m wf_contract_manifest write|check`.

The checked-in artifact will live at:

```text
contracts/workflow-api.manifest.json
```

The package is tooling rather than a new transport. It must not know about
browser targets, HTTP headers, presentation metadata, or local server URLs.

## Manifest Shape

Manifest version 1 uses this top-level structure:

```json
{
  "manifest_version": 1,
  "source": {
    "format": "openrpc",
    "openrpc_version": "1.2.6"
  },
  "operations": [],
  "components": {
    "schemas": {},
    "errors": {}
  }
}
```

Each operation contains:

```json
{
  "method": "workflow.runs.start",
  "namespace": ["workflow", "runs"],
  "action": "start",
  "params": [
    {
      "name": "deployment_id",
      "required": true,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    }
  ],
  "result": {
    "schema": {
      "$ref": "#/components/schemas/RunResult"
    }
  },
  "errors": [
    {
      "$ref": "#/components/errors/5000"
    }
  ]
}
```

The full `method` string is canonical identity. `namespace` and `action` are
derived navigation metadata and must never replace it.

Operations are sorted lexically by method. Parameter order remains the order
published by OpenRPC because it is part of the generated method description.
Component keys are sorted for deterministic serialization.

## Schema Preservation Rules

The manifest preserves JSON Schema values and local `$ref` graphs. It does not
inline shared schemas or translate them into another schema language.

Normalization recursively removes generated `title` fields only. It retains:

- descriptions and defaults;
- required arrays;
- optional parameter flags;
- explicit nullability;
- `anyOf`, `oneOf`, `not`, `if`, and `then`;
- enums, constants, and discriminators;
- numeric, string, and array constraints;
- object properties and `additionalProperties`; and
- unknown future JSON Schema keywords.

Optionality and nullability remain distinct. A parameter with `required: false`
may be omitted. A schema union containing `{ "type": "null" }` permits an
explicit null. Neither implies the other.

`additionalProperties` retains its three states:

- absent: JSON Schema's default behavior;
- `true`: explicitly extensible provider data;
- `false`: explicitly closed data.

An empty schema `{}` remains an unconstrained JSON value. It must not be
rewritten as an object schema.

## Validation

Generation fails with `ManifestError` and a concrete document path when:

- the OpenRPC document has an unsupported top-level structure;
- method names are absent, malformed, or duplicated;
- params, result, or error entries are malformed;
- a success result is a generic object instead of a named contract;
- a local `$ref` is dangling or points into an unsupported component namespace;
- an external `$ref` is encountered; or
- manifest serialization cannot produce the canonical structure.

Unknown JSON Schema keywords are preserved rather than rejected. The first
slice validates the manifest envelope and reference graph, not the complete
JSON Schema vocabulary that a later Effect translator must support.

The current method count of 70 is a migration baseline assertion, not a hard
generator limit. Method 71 should require an intentional fixture/assertion
update and manifest regeneration, not generator code changes.

## Deterministic Workflow

The supported commands are:

```powershell
.venv\Scripts\python.exe -m wf_contract_manifest write
.venv\Scripts\python.exe -m wf_contract_manifest check
```

`write` generates canonical UTF-8 JSON with stable indentation and a trailing
newline. It updates only `contracts/workflow-api.manifest.json`.

`check` regenerates in memory and byte-compares with the checked-in artifact.
On drift, it exits non-zero with a concise instruction to run `write`. It does
not overwrite files.

Generation uses a temporary local workflow store. No temporary path, server
target, `/rpc` path, header, credential value, or environment-specific state may
enter the manifest.

## Testing Strategy

### Pure Normalization Tests

Synthetic OpenRPC fixtures will verify:

- lexical operation and component sorting;
- preserved parameter order;
- optional versus nullable parameters;
- absent, true, and false `additionalProperties`;
- union and conditional schemas;
- generated-title removal;
- preservation of unknown schema keywords;
- duplicate method rejection;
- dangling and external reference rejection; and
- deterministic serialization.

### Real Contract Integration

An integration test will generate from `create_rpc_app(...)` and assert:

- 70 unique methods;
- 126 schema components at the initial baseline;
- zero generic success results;
- all local references resolve;
- the five known union result components remain unions;
- auth results do not expose a credential `payload` property; and
- provider-extension schemas retain explicit `additionalProperties: true`.

### Drift Gate

A final test regenerates the complete manifest and compares it with
`contracts/workflow-api.manifest.json`. Python contract changes therefore fail
until the shared artifact is intentionally regenerated and reviewed.

## TypeScript And Security Boundaries

The manifest describes all server operations. It does not authorize their use.
Future TypeScript work must keep these concepts separate:

- `WorkflowOperationName`: generated inventory of all wire operations;
- `SupportedOperationName`: operations implemented by the Effect client;
- `BrowserAllowedOperationName`: authored Hono security/product allowlist;
- `OperationMeta`: authored labels, explanations, idempotency, equivalent CLI,
  and semantic interpretation.

The first slice changes none of them. In particular, generating a 70-operation
inventory must not automatically expose admin writes through the browser proxy.

The following remain handwritten throughout the migration:

- evidence capture and redaction;
- target policy, timeouts, and byte limits;
- JSON-RPC and domain error mapping;
- labels, CLI equivalents, and result interpretation;
- snake-case to camel-case presentation projections; and
- console, demo, and presentation view models.

## Follow-Up Sequence

After the manifest slice:

1. Completed: generate TypeScript operation names and raw request/result types;
2. Completed: build a fail-closed JSON Schema-to-Effect translator against
   representative schemas before applying it broadly;
3. Completed: migrate the existing 12 RPC definitions by domain while
   comparing old and generated decoders. The test-only parity harness covers
   all 24 payload/result sides and retains frozen pre-migration schemas that pin
   eight old run-result mismatches. Runtime run schemas now follow the canonical
   manifest: complete interrupts for inspect/start/resume and a full run
   envelope with canonical frame identifiers for trace;
4. remove duplicated operation-name guards only after equivalent generated
   inventory is in use; and
5. expand client coverage when a product caller needs each operation.

Direct reverse conversion through newer Effect APIs may be reconsidered only
after checking version compatibility with the repository's pinned Effect and
`@effect/rpc` versions. This design does not require an Effect upgrade.

### Representative Effect Translator Boundary

The completed prototype translates boolean schemas, primitive `type` schemas,
primitive `const` and `enum`, numeric and collection constraints, objects,
`anyOf`, local component references, and structurally guarded recursive
reference graphs. Tests exercise both synthetic contracts and checked
`HealthResult` / `RunResult`
manifest components.

The translator returns a typed `JsonSchemaTranslationError` and fails closed on
unknown keywords, external or dangling references, `oneOf`, `allOf`,
conditionals, `not`, and typed additional properties mixed with fixed fields.
Required names supplied only through `additionalProperties` are also outside
the representative subset, as are property names that collide with the object
prototype. Those constructs must not be approximated with a broader Effect
schema. Recursive translation is covered synthetically; checked manifest
coverage currently exercises representative non-recursive components and a
real rejected `oneOf` boundary. The translator is not exported from the package
root. Generated runtime use covers all 12 authored RPCs; it does not change
service dispatch, operation metadata, or browser authorization.

Generated runtime schemas apply an iterative 64-container value-depth check to
requests and responses before Effect decoding. Effect's recursive schema
decoder does not independently prevent stack exhaustion on adversarially deep
values; the translator's
structural recursion guard prevents non-productive schema cycles, while the
runtime guard bounds values presented to recursive decoders.

The authored-RPC parity harness found no additional translator blockers for
the current 12 operations. Health, sources, artifacts, deployments, and run
list agree on representative accepted and rejected values. Frozen
pre-migration schemas preserve the former differences: reduced interrupts for
run inspect/start/resume and a compact trace page without canonical frame
identifiers. Runtime decoding deliberately follows the manifest instead of
broadening the translator or retaining those incomplete wire shapes.

## Success Criteria

- The shared manifest is deterministic and checked in.
- `check` detects any Python/OpenRPC drift without modifying files.
- All 70 methods and their request/result/error contracts are represented.
- Every local reference resolves.
- Auth payload values remain absent from public result schemas.
- No TypeScript runtime or browser allowlist behavior changes.
- The manifest is sufficient input for the next TypeScript generation slice.
