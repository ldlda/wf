import { Rpc, RpcGroup } from "@effect/rpc";
import { Schema } from "effect";

const NonNegativeIntegerSchema = Schema.Number.pipe(
  Schema.int(),
  Schema.between(0, Number.MAX_SAFE_INTEGER),
);

export const SourceSummarySchema = Schema.Struct({
  id: Schema.String,
  kind: Schema.String,
  enabled: Schema.Boolean,
  description: Schema.NullOr(Schema.String),
  tool_count: NonNegativeIntegerSchema,
  node_spec_count: NonNegativeIntegerSchema,
  reducer_count: NonNegativeIntegerSchema,
  prompt_count: NonNegativeIntegerSchema,
  resource_count: NonNegativeIntegerSchema,
});

export const WorkflowHealthPayloadSchema = Schema.Struct({});
export const WorkflowHealthResultSchema = Schema.Struct({
  status: Schema.Literal("ok"),
  store_root: Schema.String,
});

export const WorkflowHealth = Rpc.make("workflow.health", {
  payload: WorkflowHealthPayloadSchema,
  success: WorkflowHealthResultSchema,
  error: Schema.Never,
});

export const WorkflowSourcesListPayloadSchema = Schema.Struct({
  cursor: Schema.optional(Schema.String),
  limit: Schema.optional(
    Schema.Number.pipe(Schema.int(), Schema.between(1, 100)),
  ),
});
export const WorkflowSourcesListResultSchema = Schema.Struct({
  sources: Schema.Array(SourceSummarySchema),
  next_cursor: Schema.NullOr(Schema.String),
  total: NonNegativeIntegerSchema,
});

export const WorkflowSourcesList = Rpc.make("workflow.sources.list", {
  payload: WorkflowSourcesListPayloadSchema,
  success: WorkflowSourcesListResultSchema,
  error: Schema.Never,
});

export const WorkflowRpcs = RpcGroup.make(WorkflowHealth, WorkflowSourcesList);
