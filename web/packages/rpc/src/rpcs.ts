import { Rpc, RpcGroup } from "@effect/rpc";
import { Schema } from "effect";

export const SourceSummarySchema = Schema.Struct({
  id: Schema.String,
  kind: Schema.String,
  enabled: Schema.Boolean,
  description: Schema.NullOr(Schema.String),
  tool_count: Schema.Number,
  node_spec_count: Schema.Number,
  reducer_count: Schema.Number,
  prompt_count: Schema.Number,
  resource_count: Schema.Number,
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
  total: Schema.Number,
});

export const WorkflowSourcesList = Rpc.make("workflow.sources.list", {
  payload: WorkflowSourcesListPayloadSchema,
  success: WorkflowSourcesListResultSchema,
  error: Schema.Never,
});

export const WorkflowRpcs = RpcGroup.make(WorkflowHealth, WorkflowSourcesList);
