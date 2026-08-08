import { Schema } from "effect";
import { afterEach, describe, expect, it, vi } from "vitest";

describe("run operation registry", () => {
  afterEach(() => {
    vi.resetModules();
    vi.doUnmock("./rpcs.js");
  });

  it("decodes start results with the start success schema", async () => {
    vi.doMock("./rpcs.js", async () => {
      const actual = await vi.importActual<typeof import("./rpcs.js")>(
        "./rpcs.js",
      );
      return {
        ...actual,
        WorkflowRunsStartResultSchema: Schema.Struct({
          start_only: Schema.String,
          next_actions: Schema.Struct({
            can_continue: Schema.Boolean,
            can_save_now: Schema.NullOr(Schema.Boolean),
            recommended_next_tool: Schema.NullOr(Schema.String),
            reason: Schema.String,
            patch_examples: Schema.Array(Schema.Unknown),
            warnings: Schema.Array(Schema.String),
          }),
        }),
      };
    });

    const { getOperationMeta } = await import("./method-registry.js");
    const operation = getOperationMeta("workflow.runs.start");
    if (operation === undefined) throw new Error("missing start operation");

    expect(() =>
      operation.interpret({
        start_only: "ok",
        next_actions: {
          can_continue: false,
          can_save_now: null,
          recommended_next_tool: null,
          reason: "done",
          patch_examples: [],
          warnings: [],
        },
      }),
    ).not.toThrow();
  });

  it("decodes resume results with the resume success schema", async () => {
    vi.doMock("./rpcs.js", async () => {
      const actual = await vi.importActual<typeof import("./rpcs.js")>(
        "./rpcs.js",
      );
      return {
        ...actual,
        WorkflowRunsResumeResultSchema: Schema.Struct({
          resume_only: Schema.String,
          next_actions: Schema.Struct({
            can_continue: Schema.Boolean,
            can_save_now: Schema.NullOr(Schema.Boolean),
            recommended_next_tool: Schema.NullOr(Schema.String),
            reason: Schema.String,
            patch_examples: Schema.Array(Schema.Unknown),
            warnings: Schema.Array(Schema.String),
          }),
        }),
      };
    });

    const { getOperationMeta } = await import("./method-registry.js");
    const operation = getOperationMeta("workflow.runs.resume");
    if (operation === undefined) throw new Error("missing resume operation");

    expect(() =>
      operation.interpret({
        resume_only: "ok",
        next_actions: {
          can_continue: false,
          can_save_now: null,
          recommended_next_tool: null,
          reason: "done",
          patch_examples: [],
          warnings: [],
        },
      }),
    ).not.toThrow();
  });
});
