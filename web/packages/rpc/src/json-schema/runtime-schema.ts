import { Either, Schema } from "effect";
import type * as AST from "effect/SchemaAST";
import {
  workflowRuntimeContract,
  type WorkflowOperationParams,
  type WorkflowOperationResult,
} from "../generated/workflow-contract.js";
import { translateJsonSchema } from "./translator.js";

type RuntimeOperationName = keyof typeof workflowRuntimeContract.operations;
const MAX_RUNTIME_VALUE_DEPTH = 64;

type RuntimeValueFrame =
  | { readonly kind: "enter"; readonly depth: number; readonly value: unknown }
  | { readonly kind: "leave"; readonly value: object };

export interface RuntimeOperationSchemas<Name extends RuntimeOperationName> {
  readonly payload: Schema.Schema<WorkflowOperationParams<Name>, unknown, never>;
  readonly success: Schema.Schema<WorkflowOperationResult<Name>, unknown, never>;
}

const hasBoundedRuntimeValueDepth = (input: unknown): boolean => {
  const pending: RuntimeValueFrame[] = [{ kind: "enter", depth: 0, value: input }];
  // Track only the current ancestor chain so shared acyclic values remain valid.
  const active = new WeakSet<object>();
  while (pending.length > 0) {
    const current = pending.pop();
    if (current === undefined) break;
    if (current.kind === "leave") {
      active.delete(current.value);
      continue;
    }
    if (typeof current.value !== "object" || current.value === null) continue;
    if (current.depth >= MAX_RUNTIME_VALUE_DEPTH) return false;
    if (active.has(current.value)) return false;
    active.add(current.value);
    pending.push({ kind: "leave", value: current.value });
    for (const value of Object.values(current.value)) {
      pending.push({ kind: "enter", depth: current.depth + 1, value });
    }
  }
  return true;
};

const BoundedRuntimeValueSchema = Schema.Unknown.pipe(
  Schema.filter(hasBoundedRuntimeValueDepth, {
    message: () =>
      `runtime value exceeds ${MAX_RUNTIME_VALUE_DEPTH} nested containers`,
  }),
);

const translatedAst = (schema: unknown): AST.AST => {
  const translated = translateJsonSchema(schema, {
    components: workflowRuntimeContract.components,
  });
  if (Either.isLeft(translated)) {
    throw new Error(
      `checked runtime schema failed at ${translated.left.path}: ${translated.left.message}`,
    );
  }

  return translated.right.ast;
};

const payloadSchemaFor = <Name extends RuntimeOperationName>(
  name: Name,
): Schema.Schema<WorkflowOperationParams<Name>, unknown, never> => {
  // The AST and payload type are generated from the same checked operation.
  const schema = Schema.make<WorkflowOperationParams<Name>, unknown, never>(
    translatedAst(workflowRuntimeContract.operations[name].payload),
  );
  return Schema.compose(BoundedRuntimeValueSchema, schema);
};

const successSchemaFor = <Name extends RuntimeOperationName>(
  name: Name,
): Schema.Schema<WorkflowOperationResult<Name>, unknown, never> => {
  // The AST and result type are generated from the same checked operation.
  const schema = Schema.make<WorkflowOperationResult<Name>, unknown, never>(
    translatedAst(workflowRuntimeContract.operations[name].success),
  );
  return Schema.compose(BoundedRuntimeValueSchema, schema);
};

/** Returns fail-fast Effect schemas for one parity-verified authored RPC. */
export const runtimeSchemasFor = <Name extends RuntimeOperationName>(
  name: Name,
): RuntimeOperationSchemas<Name> => {
  return {
    payload: payloadSchemaFor(name),
    success: successSchemaFor(name),
  };
};
