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

  it.each([
    {
      method: "workflow.draft_workspaces.create_empty" as const,
      params: {
        workspace_id: "console.demo",
        name: "console.demo",
        title: "Console demo",
      },
      cli: "uv run wf draft create console.demo --name console.demo --title 'Console demo'",
      result: {
        workspace_id: "console.demo",
        revision: 1,
        title: "Console demo",
        status: "valid" as const,
        diagnostics: [],
        summary: {
          name: "console.demo",
          start: null,
          step_count: 0,
          route_count: 0,
          steps: [],
        },
      },
    },
    {
      method: "workflow.draft_workspaces.create_from_capability" as const,
      params: {
        workspace_id: "console.demo",
        capability_name: "local.example.echo",
        name: "console.demo",
      },
      cli: "uv run wf draft create console.demo --capability local.example.echo --name console.demo",
      result: {
        workspace_id: "console.demo",
        revision: 1,
        title: "Console demo",
        status: "valid" as const,
        diagnostics: [],
        summary: {
          name: "console.demo",
          start: "echo",
          step_count: 1,
          route_count: 1,
          steps: ["echo"],
        },
        next_actions: {
          can_continue: false,
          can_save_now: true,
          recommended_next_tool: null,
          reason: "ready",
          patch_examples: [],
          warnings: [],
        },
        wrapper_hints: {
          capability_name: "local.example.echo",
          confidence: "high" as const,
          declared_outcomes: ["ok"],
          input_map: {},
          input_schema: { type: "object" },
          missing_decisions: [],
          notes: [],
          outcome_candidates: [],
          outcome_policy: "preserve_declared" as const,
          output_map: {},
          output_schema: { type: "object" },
          state_schema: { type: "object" },
          suggested_wrapper_outcomes: ["ok"],
        },
      },
    },
    {
      method: "workflow.draft_workspaces.add_step_from_capability" as const,
      params: {
        workspace_id: "console.demo",
        revision: 1,
        step_id: "echo",
        capability_name: "local.example.echo",
        route_from_step: null,
        route_from_outcome: "ok",
        routes: { ok: "__end__" },
        input_map: { "input.text": "text" },
        bind_outputs: { text: "state.text" },
        retry: 1,
        timeout_seconds: 30,
      },
      cli: "uv run wf draft add capability console.demo --revision 1 --step echo --capability local.example.echo --route ok=__end__ --input input.text=text --bind-output text=state.text --retry 1 --timeout-seconds 30",
      result: {
        workspace_id: "console.demo",
        revision: 2,
        title: "Console demo",
        status: "valid" as const,
        diagnostics: [],
        summary: {
          name: "console.demo",
          start: "echo",
          step_count: 1,
          route_count: 1,
          steps: ["echo"],
        },
        draft: {
          name: "console.demo",
          start: "echo",
          steps: { echo: { use: "local.example.echo" } },
        },
      },
    },
    {
      method: "workflow.draft_workspaces.update_capability_step" as const,
      params: {
        workspace_id: "console.demo",
        revision: 2,
        step_id: "echo",
        update: { desc: "Echo text", retry: 2, timeout_seconds: 45 },
      },
      cli: "uv run wf draft update capability console.demo --revision 2 --step echo --description 'Echo text' --retry 2 --timeout-seconds 45",
      result: {
        workspace_id: "console.demo",
        revision: 3,
        title: "Console demo",
        status: "valid" as const,
        diagnostics: [],
        summary: {
          name: "console.demo",
          start: "echo",
          step_count: 1,
          route_count: 1,
          steps: ["echo"],
        },
        draft: {
          name: "console.demo",
          start: "echo",
          steps: { echo: { use: "local.example.echo" } },
        },
      },
    },
    {
      method: "workflow.draft_workspaces.set_route" as const,
      params: {
        workspace_id: "console.demo",
        revision: 3,
        step_id: "echo",
        outcome: "ok",
        target: "__end__",
      },
      cli: "uv run wf draft set-route console.demo --revision 3 --step echo --outcome ok --to __end__",
      result: {
        workspace_id: "console.demo",
        revision: 4,
        title: "Console demo",
        status: "valid" as const,
        diagnostics: [],
        summary: {
          name: "console.demo",
          start: "echo",
          step_count: 1,
          route_count: 1,
          steps: ["echo"],
        },
        draft: {
          name: "console.demo",
          start: "echo",
          steps: { echo: { use: "local.example.echo" } },
        },
      },
    },
    {
      method: "workflow.draft_workspaces.validate" as const,
      params: { workspace_id: "console.demo" },
      cli: "uv run wf draft validate console.demo",
      result: {
        workspace_id: "console.demo",
        revision: 4,
        title: "Console demo",
        status: "valid" as const,
        diagnostics: [],
        summary: {
          name: "console.demo",
          start: "echo",
          step_count: 1,
          route_count: 1,
          steps: ["echo"],
        },
      },
    },
  ])("registers and interprets $method", async (testCase) => {
    const { getOperationMeta } = await import("./method-registry.js");
    const operation = getOperationMeta(testCase.method);
    if (operation === undefined) throw new Error(`missing ${testCase.method}`);

    expect(operation.equivalentCli(testCase.params)).toBe(testCase.cli);
    expect(operation.interpret(testCase.result)).toMatchObject({
      workspaceId: "console.demo",
      revision: testCase.result.revision,
      title: "Console demo",
      status: "valid",
      summary: {
        name: "console.demo",
        start: testCase.result.summary.start,
        stepCount: testCase.result.summary.step_count,
      },
      draft: "draft" in testCase.result ? testCase.result.draft : null,
    });
  });
});
