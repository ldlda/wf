# Composite Input Expressions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let node-local inputs recursively combine workflow paths and JSON literals in arrays and objects, then author the same canonical value from the Workflow Console.

**Architecture:** Extract canonical input bindings and strict JSON helpers from the step model into focused core modules. Resolve every node-local binding through one shared runtime evaluator, validate expression leaves against capability and workflow schemas at the authoring seam, and carry the same `StepInputBinding` union through persistence, API transports, generated TypeScript contracts, and a recursive console editor. Final workflow-output bindings deliberately remain the existing simple `InputBinding` union.

**Tech Stack:** Python 3.14, Pydantic 2, JSON Schema Draft 2020-12, pytest, Typer, JSON-RPC/OpenRPC, MCP, React 19, TypeScript, Effect Schema, Valibot-style authored domain decoders, Vitest, Testing Library, Vite.

## Global Constraints

- `InputExpression` supports only `literal`, `path`, `array`, and `object` variants; do not add arithmetic, interpolation, conditions, reducers, transforms, or capability calls.
- `NodeUse.input`, `SubgraphNode.input`, and `InterruptNode.request` use `StepInputBinding`; workflow final outputs continue using `InputBinding`.
- Existing path/value bindings retain their current canonical JSON and remain preferred for whole-field assignments.
- Expression documents allow at most 64 recursive container levels and 1,024 total expression/literal-container nodes.
- Known schema incompatibility and unsupported known-schema composition fail before mutation. Paths without an authoring-time source schema are marked deferred and remain runtime-validated.
- Compatibility maps must reject expression-bearing lists they cannot reproduce exactly. They must never flatten or discard expressions.
- CLI inline flags remain path/value-only. Composite values enter through canonical `--bindings-file` JSON.
- The first recursive console editor appears only for selected capability-step inputs. Subgraph and interrupt expressions must round-trip without lossy editing until Slice 8.
- Preserve revision checks, atomic mutation, ordered bindings, explicit null, unsupported-record repair gating, and mobile inspector behavior.
- Use TDD for every task. Add comments/docstrings around bounded recursion, schema normalization, and compatibility rejection. Do not modify Serena configuration.

---

## File Structure

### Canonical Core

- `src/wf_core/models/json_values.py`: strict finite JSON type, validation, and bounded literal-container walking.
- `src/wf_core/models/input_bindings.py`: simple bindings, recursive expressions, expression limits, and `StepInputBinding`.
- `src/wf_core/models/steps.py`: step models using and re-exporting canonical binding names.
- `src/wf_core/runtime/input_bindings.py`: shared recursive expression and binding resolver.
- `src/wf_core/validation/steps.py`: structural path, overlap, and recursive expression-source validation.
- `src/wf_artifacts/drafts/models.py`: persisted draft node-use, subgraph, and interrupt payloads.

### Authoring And Public Surfaces

- `src/wf_api/schema_projection.py`: bounded schema navigation/normalization shared by path and expression validation.
- `src/wf_api/input_expressions.py`: schema-directed expression validation and source-schema projection.
- `src/wf_api/draft_authoring.py`: atomic capability binding replacement using the new validator.
- `src/wf_api/surface.py`, `service.py`, `draft_updates.py`, `capabilities.py`: `StepInputBinding` public signatures.
- `src/wf_transport_rpc_http/models.py`, `client/drafts.py`: JSON-RPC models and remote client signatures.
- `src/wf_mcp/workflow_surface/models.py`: MCP request models with the same node-local union.
- `src/wf_cli/commands/draft_options.py`: distinct step-input and workflow-output bindings-file adapters.
- `src/wf_authoring/builder/mapping.py`: authoring-friendly normalization into `StepInputBinding`.
- `src/wf_authoring/builder/core.py` and `src/wf_authoring/subgraph.py`: builder signatures for node, subgraph, and interrupt inputs.
- `src/wf_authoring/ops/sequences.py`: truthful non-empty schemas for `first_item` and `last_item`.

### Contract And Console

- `contracts/workflow-api.manifest.json`: regenerated transport-neutral contract.
- `web/packages/rpc/src/generated/workflow-contract.ts`: regenerated TypeScript wire contract.
- `web/packages/rpc/src/json-schema/authored-rpc-fixtures.ts`: recursive authored runtime schema used by parity tests.
- `web/apps/console/src/workspace/domain/draft-workspace-models.ts`: browser `InputExpression` and `StepInputBinding` types.
- `web/apps/console/src/workspace/domain/draft-authoring-client.ts`: lossless recursive binding copies.
- `web/apps/console/src/workspace/authoring/input-expression-editor.ts`: pure canonical/editor projection and serialization.
- `web/apps/console/src/workspace/authoring/InputExpressionControl.tsx`: recursive Literal/Path/Construct editor.
- `web/apps/console/src/workspace/authoring/StepInputBindingsForm.tsx`: row composition and submit gating.
- `web/apps/console/src/styles/global.css`: nested expression layout and responsive controls.

---

### Task 1: Add Canonical Input Expressions And Persistence

**Files:**

- Create: `src/wf_core/models/json_values.py`
- Create: `src/wf_core/models/input_bindings.py`
- Modify: `src/wf_core/models/steps.py`
- Modify: `src/wf_core/models/__init__.py`
- Modify: `src/wf_core/__init__.py`
- Modify: `src/wf_artifacts/drafts/models.py`
- Create: `tests/core/test_input_expressions.py`
- Modify: `tests/core/test_canonical_node_bindings.py`
- Modify: `tests/artifacts/test_draft_models.py`

**Interfaces:**

- Produces: `JsonValue`, `validate_strict_json_value(value: object) -> JsonValue`.
- Produces: `LiteralExpression`, `PathExpression`, `ArrayExpression`, `ObjectExpression`, and discriminated `InputExpression`.
- Produces: `InputExpressionBinding` and `StepInputBinding`.
- Preserves: imports of `InputBinding`, `InputPathBinding`, and `InputValueBinding` from `wf_core.models.steps` for real existing callers.

- [x] **Step 1: Write failing model and persistence tests**

Add tests that parse and round-trip this exact binding through `NodeUse`, `SubgraphNode`, `InterruptNode`, `DraftUseStep`, `DraftSubgraphPayload`, and `DraftInterruptPayload`:

```python
COMPOSITE_BINDING = {
    "target": "request",
    "expression": {
        "kind": "object",
        "fields": {
            "items": {
                "kind": "array",
                "items": [
                    {"kind": "path", "path": "state.foo"},
                    {"kind": "literal", "value": "wowcool"},
                ],
            },
            "separator": {"kind": "literal", "value": " "},
        },
    },
}
```

Assert that workflow final-output parsing rejects the same record, old path/value bindings dump unchanged, extra fields fail, non-finite/Python-only values fail, depth 65 fails, and expression node 1,025 fails. Include literal JSON containers in both depth and node-budget tests.

- [x] **Step 2: Run the model tests and verify RED**

Run:

```powershell
uv run pytest tests/core/test_input_expressions.py tests/core/test_canonical_node_bindings.py tests/artifacts/test_draft_models.py -q
```

Expected: failures because expression models and `StepInputBinding` do not exist.

- [x] **Step 3: Extract strict JSON and implement the recursive models**

Move the existing recursive `JsonValue` and strict validator into `json_values.py`. In `input_bindings.py`, define the recursive discriminated union and validate raw expression limits before Pydantic recursively constructs models:

```python
type InputExpression = Annotated[
    LiteralExpression
    | PathExpression
    | ArrayExpression
    | ObjectExpression,
    Field(discriminator="kind"),
]

class InputExpressionBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: LocalPath
    expression: InputExpression

    @field_validator("expression", mode="before")
    @classmethod
    def check_limits(cls, value: object) -> object:
        validate_input_expression_limits(value, max_depth=64, max_nodes=1_024)
        return value

StepInputBinding = Annotated[
    InputPathBinding | InputValueBinding | InputExpressionBinding,
    Field(union_mode="left_to_right"),
]
```

The limit walker must inspect the tagged expression structure and nested literal containers without recursively trusting malformed fields. Raise one concise `ValueError` containing the exceeded limit and expression location.

- [x] **Step 4: Migrate only node-local persisted models**

Use `list[StepInputBinding]` for `NodeUse.input`, `SubgraphNode.input`, `InterruptNode.request`, `DraftUseStep.input`, `DraftSubgraphPayload.input`, and `DraftInterruptPayload.request`. Keep `Workflow.output` and `WorkflowDraft.output` on `list[InputBinding]`.

Retain the existing deprecated-map normalization order. Canonical expression records pass through untouched; deprecated maps can synthesize only path/value records and still reject mixed canonical/deprecated fields.

- [x] **Step 5: Verify and commit**

Run the command from Step 2 plus:

```powershell
uv run basedpyright --level error src/wf_core/models src/wf_artifacts/drafts
```

Expected: all pass.

Commit:

```powershell
git add src/wf_core/models src/wf_core/__init__.py src/wf_artifacts/drafts/models.py tests/core/test_input_expressions.py tests/core/test_canonical_node_bindings.py tests/artifacts/test_draft_models.py
git commit -m "feat: model composite step inputs"
```

---

### Task 2: Resolve And Validate Expressions In Core Execution

**Files:**

- Create: `src/wf_core/runtime/input_bindings.py`
- Modify: `src/wf_core/runtime/ops/nodes.py`
- Modify: `src/wf_core/runtime/subgraphs.py`
- Modify: `src/wf_core/runtime/ops/interrupts.py`
- Modify: `src/wf_core/validation/steps.py`
- Create: `tests/core/test_input_expression_runtime.py`
- Modify: `tests/core/test_subgraph_step.py`
- Modify: `tests/core/test_execution_results.py`
- Modify: `tests/core/test_mapping_validation.py`

**Interfaces:**

- Consumes: `StepInputBinding` and `InputExpression` from Task 1.
- Produces: `resolve_input_expression(expression, *, state, workflow_input, context, label, location) -> JsonValue`.
- Produces: `resolve_step_input_bindings(bindings, *, state, workflow_input, context, label) -> dict[str, Any]`.

- [x] **Step 1: Write failing shared-resolution tests**

Cover nested object/array resolution, ordering, explicit null, input/state/context paths, missing paths, and exact locations such as `node 'concat' input request.items[0]`. Add integration cases proving the same expression works in a normal node, a prepared subgraph input, and an interrupt request.

```python
resolved = resolve_step_input_bindings(
    [InputExpressionBinding.model_validate(COMPOSITE_BINDING)],
    state={"foo": "hello"},
    workflow_input={},
    context={},
    label="node 'concat' input",
)
assert resolved == {"request": {"items": ["hello", "wowcool"], "separator": " "}}
```

Add validation tests proving expression path leaves use the same declared-root checks as direct path bindings and that an expression target overlaps `request.title` when another binding owns `request`.

- [x] **Step 2: Run focused core tests and verify RED**

```powershell
uv run pytest tests/core/test_input_expression_runtime.py tests/core/test_subgraph_step.py tests/core/test_execution_results.py tests/core/test_mapping_validation.py -q
```

Expected: expression bindings hit unsupported-binding branches.

- [x] **Step 3: Implement one shared resolver**

Move simple path/value resolution out of `ops/nodes.py` and `subgraphs.py`. Recursively resolve arrays and objects, extend the location with `[index]` and `.field`, and wrap path/local-target failures as `WorkflowExecutionError` without losing the location.

Replace the loops in normal node execution, `_start_subgraph`, and `build_interrupt_request` with `resolve_step_input_bindings`. Do not use this helper in `project_output`; that final-output path intentionally remains simple.

- [x] **Step 4: Make core structural validation exhaustive**

Change node-local validation signatures to `list[StepInputBinding]`. Recursively visit every `PathExpression` and report `INVALID_SOURCE_PATH` at `nodes[N].input[M].expression...path`. Continue validating target overlap once per top-level binding because each expression assigns its final value atomically.

- [x] **Step 5: Verify and commit**

Run Step 2 plus:

```powershell
uv run basedpyright --level error src/wf_core/runtime src/wf_core/validation
```

Commit:

```powershell
git add src/wf_core/runtime src/wf_core/validation tests/core/test_input_expression_runtime.py tests/core/test_subgraph_step.py tests/core/test_execution_results.py tests/core/test_mapping_validation.py
git commit -m "feat: resolve composite step inputs"
```

---

### Task 3: Add Schema-Directed Authoring Validation

**Files:**

- Modify: `src/wf_api/schema_projection.py`
- Create: `src/wf_api/input_expressions.py`
- Modify: `src/wf_api/draft_authoring.py`
- Modify: `src/wf_api/drafts.py`
- Modify: `src/wf_authoring/ops/sequences.py`
- Modify: `tests/wf_api/test_schema_projection.py`
- Create: `tests/wf_api/test_input_expression_validation.py`
- Modify: `tests/wf_api/test_drafts_service.py`
- Modify: `tests/wf_api/test_local_sources.py`
- Modify: `tests/authoring/test_ops.py`

**Interfaces:**

- Consumes: expression models and limits from Task 1.
- Produces: `schema_fragment_at_location(schema, location, *, label) -> JsonObject` for object fields, homogeneous arrays, tuples, additional properties, and bounded local references.
- Produces: `validate_and_project_input_expression(...) -> ExpressionProjection`, where `ExpressionProjection` contains projected input/state schemas and `deferred_paths`.

- [x] **Step 1: Write failing generalized schema-navigation tests**

Add exact cases for:

- object `properties`;
- schema-valued `additionalProperties`;
- homogeneous `items`;
- tuple `prefixItems` and out-of-range positions;
- `#/$defs/...` and `#/definitions/...`;
- cyclic, unresolved, and remote references; and
- unsupported `allOf`, `anyOf`, `oneOf`, `if`, `then`, and `else` at an expression position.

Keep `schema_fragment_at_path` as the object-path compatibility wrapper. Its existing tests must remain unchanged.

- [x] **Step 2: Write failing authoring mutation tests**

Use `set_step_input_bindings` with a `wf.std.concat` expression. Assert that literals validate at their exact array positions, missing input/state source schemas are projected from the target fragment, known incompatible source schemas reject without revision change, context paths return as deferred, overlapping targets reject, and the stored draft preserves exact expression order.

Add a compatibility test where `set_step_input_map(..., merge=True)` sees an existing expression and raises a lossless-round-trip error without mutation.

- [x] **Step 3: Run focused tests and verify RED**

```powershell
uv run pytest tests/wf_api/test_schema_projection.py tests/wf_api/test_input_expression_validation.py tests/wf_api/test_drafts_service.py tests/authoring/test_ops.py -q
```

Expected: schema navigation is object-only and capability authoring rejects expressions.

- [x] **Step 4: Implement bounded schema navigation and compatibility**

Add `schema_fragment_at_location` as the deep primitive and keep existing functions as narrow wrappers. Normalize local references before comparison. Return one of `compatible`, `incompatible`, or `unsupported` from a private schema-assignability helper:

- absent source schema: deferred;
- exact normalized equality: compatible;
- primitive source type contained by target type, with integer assignable to number: compatible;
- source `const`/`enum` wholly accepted by target `const`/`enum`: compatible;
- recursively declared arrays/objects with supported keywords: compare their members;
- known mismatch: incompatible;
- unsupported composition or constraints that cannot be proven safe: unsupported and fail closed.

Do not add a general JSON Schema subtype engine. Document this conservative supported subset in the helper docstring.

- [x] **Step 5: Integrate atomic expression projection**

In `_project_step_input_bindings`, validate the top-level target, then recursively validate the expression against that target fragment. Project missing input/state source schemas from the corresponding expression position. Keep context paths in `ExpressionProjection.deferred_paths`; they are accepted because runtime payload validation remains authoritative. Serialize only after all bindings validate so failures cannot advance the draft revision.

Update `_require_lossless_step_input_map_round_trip` tests so expression records cause a clear rejection. Do not teach map helpers to understand expressions.

- [x] **Step 6: Make sequence contracts truthful**

Add:

```python
class NonEmptySequenceInput(BaseModel):
    """Input model for operations that require at least one item."""

    items: list[Any] = Field(min_length=1)
```

Use it only for `first_item` and `last_item`; retain their defensive runtime guards. Assert generated schemas contain `minItems: 1`, while `first_item_maybe`, `first_item_or_none`, `last_item_or_none`, `length`, and `is_empty` still accept empty arrays.

In `tests/wf_api/test_local_sources.py`, inspect the qualified platform catalog and assert public `wf.std.first_item` and `wf.std.last_item` input schemas contain `minItems: 1`. Assert the public empty-aware variants do not gain that constraint.

- [x] **Step 7: Verify and commit**

Run Step 3 plus:

```powershell
uv run basedpyright --level error src/wf_api src/wf_authoring/ops/sequences.py
```

Commit:

```powershell
git add src/wf_api/schema_projection.py src/wf_api/input_expressions.py src/wf_api/draft_authoring.py src/wf_api/drafts.py src/wf_authoring/ops/sequences.py tests/wf_api tests/authoring/test_ops.py
git commit -m "feat: validate composite input schemas"
```

---

### Task 4: Carry Step Inputs Through Python API, Live OpenRPC, MCP, And CLI

**Files:**

- Modify: `src/wf_api/surface.py`
- Modify: `src/wf_api/service.py`
- Modify: `src/wf_api/draft_updates.py`
- Modify: `src/wf_api/capabilities.py`
- Modify: `src/wf_transport_rpc_http/models.py`
- Modify: `src/wf_transport_rpc_http/client/drafts.py`
- Modify: `src/wf_transport_rpc_http/__init__.py`
- Modify: `src/wf_mcp/workflow_surface/models.py`
- Modify: `src/wf_cli/commands/draft_options.py`
- Modify: `src/wf_cli/commands/drafts.py`
- Modify: `src/wf_cli/commands/draft_add.py`
- Modify: `src/wf_cli/commands/draft_update.py`
- Modify: `src/wf_cli/explain/entries.py`
- Modify: `src/wf_authoring/builder/mapping.py`
- Modify: `src/wf_authoring/builder/core.py`
- Modify: `src/wf_authoring/subgraph.py`
- Modify: `tests/wf_api/test_drafts_service.py`
- Modify: `tests/wf_transport_rpc_http/test_rpc_models.py`
- Modify: `tests/wf_transport_rpc_http/test_client.py`
- Modify: `tests/wf_transport_rpc_http/test_openrpc_contract.py`
- Modify: `tests/wf_mcp/workflow_surface/test_drafts.py`
- Modify: `tests/wf_cli/test_app.py`
- Modify: `tests/wf_cli/test_remote_target.py`
- Modify: `tests/wf_cli/test_explain.py`
- Modify: `tests/authoring/test_builder.py`
- Modify: `tests/authoring/test_subgraph.py`

**Interfaces:**

- Consumes: `StepInputBinding` from Task 1 and authoring validation from Task 3.
- Produces: node-local API parameters typed as `Sequence[StepInputBinding]` / `list[StepInputBinding]`.
- Preserves: workflow-output operations and CLI parser on `InputBinding`.

- [x] **Step 1: Write failing surface parity tests**

Submit `COMPOSITE_BINDING` through `WorkflowBuilder.use`, `use_ref`, `subgraph`, and `interrupt`, then through local API calls, JSON-RPC params, remote client, MCP requests, `wf draft add capability --bindings-file`, `wf draft set-input --bindings-file`, and `wf draft update capability --bindings-file`. Assert exact nested JSON reaches the resulting model or service.

Add negative tests proving inline `--map`/`--value` do not claim expression syntax and workflow-output `--bindings-file` rejects `expression`.

Pin `wf draft set-input --help` and explain output so they say composite expressions belong in the canonical bindings file. Do not describe indexed local targets or an inline expression mini-language.

- [x] **Step 2: Run focused parity tests and verify RED**

```powershell
uv run pytest tests/authoring/test_builder.py tests/authoring/test_subgraph.py tests/wf_transport_rpc_http/test_rpc_models.py tests/wf_transport_rpc_http/test_client.py tests/wf_transport_rpc_http/test_openrpc_contract.py tests/wf_mcp/workflow_surface/test_drafts.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py tests/wf_cli/test_explain.py -q
```

Expected: transport models still parse node-local lists as `InputBinding`.

- [x] **Step 3: Change only node-local public signatures**

Update focused replacement, capability add/update, generic draft step payloads, subgraph inputs, and interrupt requests to `StepInputBinding`. Keep workflow output replacements, wrapper final output, and output bindings narrow.

Rename the authoring helper alias to `StepInputBindingArg = StepInputBinding | Mapping[str, object]`. Make `normalize_step_input_bindings(...) -> list[StepInputBinding]` parse `expression` records through `InputExpressionBinding`, and use it for builder node, subgraph, and interrupt inputs. Deprecated map/value sugar continues producing only simple bindings. Do not widen any builder helper that represents final workflow output.

In CLI parsing, replace the single adapter with:

```python
_STEP_INPUT_BINDINGS_ADAPTER = TypeAdapter(list[StepInputBinding])
_WORKFLOW_OUTPUT_BINDINGS_ADAPTER = TypeAdapter(list[InputBinding])
```

Use the first only in node-local `--bindings-file` commands. Keep command evidence honest: composite payloads render as bindings-file-only, never invented inline flags.

- [x] **Step 4: Verify OpenRPC distinguishes both unions**

Assert the live OpenRPC document generated from the updated Python models makes the `set_step_input_bindings` component reach `InputExpressionBinding`, while workflow-output operations do not. Assert deprecated map payloads remain map-shaped and cannot carry expressions. Do not inspect or regenerate the checked manifest in this task; Task 5 performs that deterministic artifact update.

- [x] **Step 5: Verify and commit**

Run Step 2 plus:

```powershell
uv run basedpyright --level error src/wf_api src/wf_transport_rpc_http src/wf_mcp/workflow_surface src/wf_cli
```

Commit:

```powershell
git add src/wf_api src/wf_transport_rpc_http src/wf_mcp/workflow_surface src/wf_cli src/wf_authoring/builder src/wf_authoring/subgraph.py tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http tests/wf_mcp/workflow_surface/test_drafts.py tests/wf_cli tests/authoring/test_builder.py tests/authoring/test_subgraph.py
git commit -m "feat: expose composite step inputs"
```

---

### Task 5: Regenerate And Decode The TypeScript Contract

**Files:**

- Modify: `tests/wf_contract_manifest/test_generate.py`
- Regenerate: `contracts/workflow-api.manifest.json`
- Regenerate: `web/packages/rpc/src/generated/workflow-contract.ts`
- Modify: `web/packages/rpc/src/generated/workflow-contract.test.ts`
- Modify: `web/packages/rpc/src/json-schema/authored-rpc-fixtures.ts`
- Modify: `web/packages/rpc/src/json-schema/rpc-parity.test.ts`
- Modify: `web/packages/rpc/src/method-registry.ts`
- Modify: `web/packages/rpc/src/method-registry.test.ts`
- Modify: `web/apps/console/src/workspace/domain/draft-workspace-models.ts`
- Modify: `web/apps/console/src/workspace/domain/draft-workspace-models.test.ts`
- Modify: `web/apps/console/src/workspace/domain/draft-authoring-client.ts`
- Modify: `web/apps/console/src/workspace/domain/draft-authoring-client.test.ts`
- Modify: `web/apps/console/src/workspace/authoring/useDraftAuthoring.ts`
- Modify: `web/apps/console/src/workspace/authoring/useDraftAuthoring.test.tsx`
- Modify: `web/apps/console/src/workspace/authoring/CapabilityNodeForm.tsx`
- Modify: `web/apps/console/src/workspace/authoring/CapabilityNodeForm.test.tsx`

**Interfaces:**

- Produces: generated `InputExpression`, `InputExpressionBinding`, and `StepInputBinding` wire types.
- Produces: browser domain types with the same recursive discriminators.
- Produces: lossless `copyInputExpression` and `copyStepInputBinding` helpers.

- [x] **Step 1: Write failing manifest and authored-schema tests**

Assert the generated manifest contains recursive expression definitions, node-local draft fields reference `StepInputBinding`, and workflow output references only `InputBinding`. Add runtime parity fixtures for a nested array/object expression and an over-specified expression that must fail.

- [x] **Step 2: Regenerate checked contracts**

Run in dependency order:

```powershell
uv run python -m wf_contract_manifest write
pnpm --dir web --filter @lda/workflow-rpc contract:write
pnpm --dir web --filter @lda/workflow-rpc contract:check
```

Do not edit either generated file by hand.

- [x] **Step 3: Add the recursive authored Effect schema**

Use `Schema.suspend` so parity has a real runtime decoder:

```ts
type InputExpression =
  | { readonly kind: "literal"; readonly value: JsonValue }
  | { readonly kind: "path"; readonly path: GraphSourcePath }
  | { readonly kind: "array"; readonly items: ReadonlyArray<InputExpression> }
  | { readonly kind: "object"; readonly fields: Readonly<Record<string, InputExpression>> };

const InputExpressionSchema: Schema.Schema<InputExpression> = Schema.suspend(() =>
  Schema.Union(LiteralExpressionSchema, PathExpressionSchema, ArrayExpressionSchema, ObjectExpressionSchema),
);
```

Keep workflow-output authored fixtures on the simple union.

Make `inputBindingCliArgs` exhaustive over `StepInputBinding`. Path/value records keep their current equivalent CLI rendering. Any expression record marks the operation non-equivalent with `input_bindings (use --bindings-file)`; it must not stringify the expression into a fake `--value` flag.

- [x] **Step 4: Add browser domain types and lossless copies**

Define `InputBinding` as path/value and `StepInputBinding` as `InputBinding | InputExpressionBinding`. Deep-copy arrays, object fields, literal JSON containers, and structural paths. Never use `JSON.parse(JSON.stringify(...))`, because the helper must preserve strict typing and produce useful branch exhaustiveness errors.

Change `SetStepInputBindingsInput`, capability add/update inputs, `DraftAuthoringClient`, and `useDraftAuthoring.setStepInputs` to `ReadonlyArray<StepInputBinding>`. Update every copy helper with an exhaustive `expression` branch. `CapabilityNodeForm` may continue creating simple bindings in this slice, but its callback and controller types must accept the complete node-local union without dropping an expression returned by canonical rehydration.

- [x] **Step 5: Verify and commit**

```powershell
uv run pytest tests/wf_contract_manifest/test_generate.py tests/wf_contract_manifest/test_committed_manifest.py -q
pnpm --dir web --filter @lda/workflow-rpc test
pnpm --dir web --filter @lda/workflow-rpc typecheck
pnpm --dir web --filter @lda/console test -- src/workspace/domain/draft-workspace-models.test.ts src/workspace/domain/draft-authoring-client.test.ts src/workspace/authoring/useDraftAuthoring.test.tsx src/workspace/authoring/CapabilityNodeForm.test.tsx
```

Commit:

```powershell
git add tests/wf_contract_manifest contracts/workflow-api.manifest.json web/packages/rpc web/apps/console/src/workspace/domain web/apps/console/src/workspace/authoring/useDraftAuthoring.ts web/apps/console/src/workspace/authoring/useDraftAuthoring.test.tsx web/apps/console/src/workspace/authoring/CapabilityNodeForm.tsx web/apps/console/src/workspace/authoring/CapabilityNodeForm.test.tsx
git commit -m "feat: decode composite step inputs"
```

---

### Task 6: Build The Pure Recursive Console Projection

**Files:**

- Create: `web/apps/console/src/workspace/authoring/input-expression-editor.ts`
- Create: `web/apps/console/src/workspace/authoring/input-expression-editor.test.ts`
- Modify: `web/apps/console/src/workspace/authoring/selected-step-dataflow.ts`
- Modify: `web/apps/console/src/workspace/authoring/selected-step-dataflow.test.ts`
- Modify: `web/apps/console/src/workspace/authoring/canonical-capability-form.ts`
- Modify: `web/apps/console/src/workspace/authoring/canonical-capability-form.test.ts`
- Modify: `web/apps/console/src/workspace/authoring/authoring-graph.test.ts`
- Modify: `web/apps/console/src/workspace/schema-form/schema-field.ts`
- Modify: `web/apps/console/src/workspace/schema-form/schema-field.test.ts`

**Interfaces:**

- Consumes: browser `InputExpression` and `StepInputBinding` from Task 5.
- Produces: recursive `ExpressionEditorState`.
- Produces: `projectExpressionEditorState(expression, schema)`, `serializeExpressionEditorState(state)`, and `validateExpressionEditorState(state, schema)`.
- Produces: canonical rows that preserve unsupported records and block replacement.

- [x] **Step 1: Write failing round-trip tests**

Use this exact editor-state union:

```ts
export type ExpressionEditorState =
  | { readonly kind: "literal"; readonly value: unknown; readonly touched: boolean }
  | { readonly kind: "path"; readonly path: string; readonly touched: boolean }
  | { readonly kind: "array"; readonly items: ReadonlyArray<ExpressionEditorState> }
  | { readonly kind: "object"; readonly fields: ReadonlyArray<{ readonly name: string; readonly value: ExpressionEditorState }> };
```

Assert canonical expression -> editor state -> canonical expression semantic equality for nested arrays/objects, field order, explicit null, structural paths, empty arrays allowed by schema, `minItems`, `maxItems`, required fields, schema-valued `additionalProperties`, and boolean additional properties. The mandated editor union stores `path` as a string, so structural path objects normalize through the canonical formatter at projection and serialize deterministically as strings, including after immutable state copies. Representation-lossless copying of canonical expressions remains the responsibility of the Task 5 copy helpers outside this editor state.

Assert cyclic/unresolved/remote refs and unsupported compositions produce an `unsupported` result carrying the original canonical record, never an empty literal.

- [x] **Step 2: Run pure tests and verify RED**

```powershell
pnpm --dir web --filter @lda/console test -- src/workspace/authoring/input-expression-editor.test.ts src/workspace/authoring/selected-step-dataflow.test.ts src/workspace/authoring/canonical-capability-form.test.ts src/workspace/authoring/authoring-graph.test.ts src/workspace/schema-form/schema-field.test.ts
```

Expected: the recursive projection module does not exist.

- [x] **Step 3: Implement parser-first projection and serialization**

Reuse `resolveLocalSchemaNodeWithAncestry`, schema path formatting, and existing literal conversion helpers. Preserve object fields as ordered entries in editor state even though canonical JSON serializes them as an object. Reject duplicate field names before serialization.

Return a discriminated projection result:

```ts
export type ExpressionProjection =
  | { readonly kind: "editable"; readonly state: ExpressionEditorState }
  | { readonly kind: "unsupported"; readonly raw: InputExpression; readonly reason: string };
```

Do not add a raw JSON editing mode.

- [x] **Step 4: Integrate selected-step projection**

Teach canonical input rows to distinguish simple path/value records from expression records. An unsupported expression stays in its original row index and blocks save/clear until explicitly removed, matching existing malformed-row repair semantics.

Update `canonical-capability-form.ts` to parse the complete `StepInputBinding` union from returned drafts. Its generated creation defaults may remain simple path/value bindings, but parsing and rehydration must not classify a valid expression as malformed.

Add a graph-model regression proving one expression binding contributes one input binding to the existing summary. Do not expand nested expression leaves into fake graph bindings or additional nodes.

- [x] **Step 5: Verify and commit**

Run Step 2 and:

```powershell
pnpm --dir web --filter @lda/console typecheck
```

Commit:

```powershell
git add web/apps/console/src/workspace/authoring/input-expression-editor.ts web/apps/console/src/workspace/authoring/input-expression-editor.test.ts web/apps/console/src/workspace/authoring/selected-step-dataflow.ts web/apps/console/src/workspace/authoring/selected-step-dataflow.test.ts web/apps/console/src/workspace/authoring/canonical-capability-form.ts web/apps/console/src/workspace/authoring/canonical-capability-form.test.ts web/apps/console/src/workspace/authoring/authoring-graph.test.ts web/apps/console/src/workspace/schema-form/schema-field.ts web/apps/console/src/workspace/schema-form/schema-field.test.ts
git commit -m "feat: project composite input editors"
```

---

### Task 7: Render The Recursive Capability Input Editor

**Files:**

- Create: `web/apps/console/src/workspace/authoring/InputExpressionControl.tsx`
- Create: `web/apps/console/src/workspace/authoring/InputExpressionControl.test.tsx`
- Modify: `web/apps/console/src/workspace/authoring/StepInputBindingsForm.tsx`
- Modify: `web/apps/console/src/workspace/authoring/StepInputBindingsForm.test.tsx`
- Modify: `web/apps/console/src/workspace/authoring/SelectedCapabilityInspector.test.tsx`
- Modify: `web/apps/console/src/workspace/authoring/useDraftAuthoring.test.tsx`
- Modify: `web/apps/console/src/styles/global.css`

**Interfaces:**

- Consumes: pure editor state and serializers from Task 6.
- Produces: recursive Path/Literal/Construct controls for capability input rows.
- Preserves: `onSubmit(bindings: ReadonlyArray<StepInputBinding>)` as complete ordered replacement.

- [x] **Step 1: Write failing interaction tests**

For a concat-like schema, exercise the real sequence:

1. choose `Construct` for `items`;
2. add two items;
3. choose `Path` and enter `state.foo` for item 1;
4. choose `Literal` and enter `wowcool` for item 2;
5. choose `Literal` and enter one space for `separator`;
6. save; and
7. assert one expression binding with exact order.

Add nested object/array construction, reorder, remove, required-property, `minItems`, `maxItems`, additional-property name, duplicate-name, deferred path label, unsupported-record blocking, and mobile mounted-inspector tests.

- [x] **Step 2: Run focused React tests and verify RED**

```powershell
pnpm --dir web --filter @lda/console test -- src/workspace/authoring/InputExpressionControl.test.tsx src/workspace/authoring/StepInputBindingsForm.test.tsx src/workspace/authoring/SelectedCapabilityInspector.test.tsx src/workspace/authoring/useDraftAuthoring.test.tsx
```

Expected: Construct controls are absent.

- [x] **Step 3: Implement the recursive control**

Render a fieldset per expression level with a stable accessible name derived from its schema location. Path and Literal reuse existing controls. Construct appears only for object/array schemas. Arrays expose Add, Remove, Move up, and Move down. Objects show declared properties and named additional fields only when the schema permits them.

Use ordinary React state updates and immutable recursive helpers; do not introduce a second form library or global store. The visual hierarchy should use indentation, a quiet left rule, and compact source toggles rather than nesting full cards at every level.

- [x] **Step 4: Integrate submit gating and canonical rehydration**

Disable Save when cardinality, required fields, duplicate names, invalid paths, invalid literals, or unsupported canonical records remain. After a successful mutation, rehydrate from the returned draft instead of retaining browser-owned state.

Show `Validated when the workflow runs` beside context paths or other schema-less path sources. Known incompatible paths must display the backend diagnostic and remain unsaved.

- [x] **Step 5: Verify and commit**

Run Step 2 plus:

```powershell
pnpm --dir web --filter @lda/console typecheck
pnpm --dir web --filter @lda/console build
```

Commit:

```powershell
git add web/apps/console/src/workspace/authoring web/apps/console/src/styles/global.css
git commit -m "feat: author composite step inputs"
```

---

### Task 8: Prove The Vertical Slice And Close Documentation

**Files:**

- Create: `tests/wf_api/test_composite_input_workflow.py`
- Modify: `tests/wf_cli/test_remote_target.py`
- Modify: `web/apps/console/src/workspace/routes/DraftDetailRoute.authoring-sync.test.tsx`
- Modify: `ISSUES.md`
- Modify: `docs/current_roadmap.md`
- Modify: `docs/project_map.md`
- Move after implementation: `docs/superpowers/plans/2026-08-12-composite-input-expressions.md` to `docs/historical/superpowers/plans/2026-08-12-composite-input-expressions.md`

**Interfaces:**

- Consumes: the complete Python and browser vertical slice from Tasks 1-7.
- Produces: one regression fixture proving `wf.std.concat` receives a state-backed item plus a literal item.

- [x] **Step 1: Write the end-to-end Python test**

Create a draft with state `foo = "hello"`, a `wf.std.concat` capability step, and:

```json
{
  "target": ".",
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

Save/compile the draft and execute it with the real platform `wf.std` registry. Assert the node receives `{"items": ["hello", "wowcool"], "separator": " "}` and output equals `"hello wowcool"`.

- [x] **Step 2: Write the browser-to-RPC regression test**

Render a draft route with the concat schema, construct the expression through the form, submit, and assert the exact JSON-RPC payload for `workflow.draft_workspaces.set_step_input_bindings`. Return the canonical draft and assert the editor rehydrates the same two items.

- [x] **Step 3: Run focused vertical verification**

```powershell
uv run pytest tests/wf_api/test_composite_input_workflow.py tests/wf_cli/test_remote_target.py -q
pnpm --dir web --filter @lda/console test -- src/workspace/routes/DraftDetailRoute.authoring-sync.test.tsx
```

Expected: all pass.

- [x] **Step 4: Run final regression gates**

```powershell
uv run pytest tests/core tests/artifacts tests/authoring tests/wf_api tests/wf_transport_rpc_http tests/wf_mcp/workflow_surface tests/wf_cli tests/wf_contract_manifest -q
uv run ruff check src/wf_core src/wf_artifacts src/wf_authoring src/wf_api src/wf_transport_rpc_http src/wf_mcp/workflow_surface src/wf_cli tests/core/test_input_expressions.py tests/core/test_input_expression_runtime.py tests/wf_api/test_input_expression_validation.py tests/wf_api/test_composite_input_workflow.py
uv run ruff format --check src/wf_core src/wf_artifacts src/wf_authoring src/wf_api src/wf_transport_rpc_http src/wf_mcp/workflow_surface src/wf_cli tests/core/test_input_expressions.py tests/core/test_input_expression_runtime.py tests/wf_api/test_input_expression_validation.py tests/wf_api/test_composite_input_workflow.py
uv run basedpyright --level error
pnpm --dir web test
pnpm --dir web typecheck
pnpm --dir web build
git diff --check
```

If the full Python suite exceeds the available turn, report the exact scoped suites completed and run the repository-wide suite before calling the branch complete.

- [x] **Step 5: Update live docs and archive the plan**

Mark the composite input issue complete in `ISSUES.md`, mark Slice 5 complete in `docs/current_roadmap.md`, document `input_bindings.py` and the console expression editor in `docs/project_map.md`, and move this plan to the historical mirror path. Keep the design spec live because it describes current behavior after implementation.

- [x] **Step 6: Review and commit**

Run the repository `/review` task or the `requesting-code-review` skill against the implementation commits. Fix Critical and Important findings, rerun affected tests, then commit:

```powershell
git add ISSUES.md docs/current_roadmap.md docs/project_map.md docs/superpowers/plans/2026-08-12-composite-input-expressions.md docs/historical/superpowers/plans/2026-08-12-composite-input-expressions.md tests/wf_api/test_composite_input_workflow.py tests/wf_cli/test_remote_target.py web/apps/console/src/workspace/routes/DraftDetailRoute.authoring-sync.test.tsx
git commit -m "docs: complete composite input expressions"
```

---

## Final Acceptance Checklist

- [x] Existing path/value binding JSON remains unchanged.
- [x] Node-use, subgraph, and interrupt-request expressions parse, persist, and execute.
- [x] Workflow final-output expressions are rejected at model, API, CLI, OpenRPC, and TypeScript boundaries.
- [x] Runtime failures identify the binding target and nested expression location.
- [x] Known schema mismatches reject atomically; schema-less paths are visibly deferred to runtime.
- [x] Compatibility maps reject expression-bearing canonical lists without mutation.
- [x] Expression depth/node limits fail as validation errors, not recursion crashes.
- [x] `first_item` and `last_item` expose `minItems: 1`; empty-aware sequence operations still accept `[]`.
- [x] CLI bindings files, JSON-RPC, MCP, manifest, generated TypeScript, and browser decoders preserve exact expressions.
- [x] The console constructs `[path(state.foo), literal("wowcool")]` without indexed local targets or raw JSON editing.
- [x] The real `wf.std.concat` vertical test produces `hello wowcool`.
