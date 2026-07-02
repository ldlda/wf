import { Rpc, RpcGroup } from "@effect/rpc";
import { Schema } from "effect";

const SourceSummarySchema = Schema.Struct({
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

export const WorkflowHealth = Rpc.make("workflow.health", {
  payload: Schema.Struct({}),
  success: Schema.Struct({
    status: Schema.Literal("ok"),
    store_root: Schema.String,
  }),
  error: Schema.Never,
});

export const WorkflowSourcesList = Rpc.make("workflow.sources.list", {
  payload: Schema.Struct({
    cursor: Schema.optional(Schema.String),
    limit: Schema.optional(
      Schema.Number.pipe(Schema.greaterThan(0), Schema.lessThan(101)),
    ),
  }),
  success: Schema.Struct({
    sources: Schema.Array(SourceSummarySchema),
    next_cursor: Schema.NullOr(Schema.String),
    total: Schema.Number,
  }),
  error: Schema.Never,
});

export const WorkflowRpcs = RpcGroup.make(WorkflowHealth, WorkflowSourcesList);
