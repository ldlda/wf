import { Schema } from "effect";
import { afterEach, describe, expect, it, vi } from "vitest";

describe("run operation registry", () => {
  afterEach(() => {
    vi.resetModules();
    vi.doUnmock("./rpcs.js");
  });

  it("registers capability calls with the exact CLI and interpreted fields", async () => {
    const { getOperationMeta } = await import("./method-registry.js");
    const operation = getOperationMeta("workflow.capabilities.call");
    if (operation === undefined) throw new Error("missing capability call operation");

    expect(operation.idempotency).toBe("write");
    expect(
      operation.equivalentCli({
        qualified_name: "local.example.echo",
        payload: { text: "hello world" },
        deployment_id: "demo.default",
      }),
    ).toBe(
      "uv run wf cap call local.example.echo --input '{\"text\":\"hello world\"}' --deployment demo.default",
    );
    expect(
      operation.interpret({
        qualified_name: "local.example.echo",
        source_id: "local.example",
        kind: "node_spec",
        deployment_id: null,
        outcome: "ok",
        output: { text: "hello" },
        diagnostics: [
          {
            bound_source: null,
            code: "ok",
            logical_ref: "local.example.echo",
            message: "called",
            repair_hint: null,
            severity: "info",
          },
        ],
      }),
    ).toEqual({
      qualifiedName: "local.example.echo",
      sourceId: "local.example",
      kind: "node_spec",
      deploymentId: null,
      outcome: "ok",
      output: { text: "hello" },
      diagnostics: [
        {
          boundSource: null,
          code: "ok",
          logicalRef: "local.example.echo",
          message: "called",
          repairHint: null,
          severity: "info",
        },
      ],
    });
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
      method: "workflow.draft_workspaces.set_step_input_bindings" as const,
      params: {
        workspace_id: "console.demo",
        revision: 3,
        step_id: "render",
        bindings: [
          { path: "input.title", target: "report.title" },
          { target: "format", value: "markdown" },
        ],
      },
      cli: "uv run wf draft set-input console.demo --revision 3 --step render --map input.title=report.title --value 'format=\"markdown\"'",
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
      method: "workflow.draft_workspaces.set_step_output_bindings" as const,
      params: {
        workspace_id: "console.demo",
        revision: 4,
        step_id: "render",
        bindings: [{ source: "report", target: "state.report" }],
      },
      cli: "uv run wf draft set-output console.demo --revision 4 --step render --map report=state.report",
      result: {
        workspace_id: "console.demo",
        revision: 5,
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

  it("renders clear metadata and representable canonical input bindings", async () => {
    const { getOperationMeta } = await import("./method-registry.js");
    const operation = getOperationMeta(
      "workflow.draft_workspaces.update_capability_step",
    );
    if (operation === undefined) throw new Error("missing update operation");

    expect(
      operation.equivalentCli({
        workspace_id: "console.demo",
        revision: 2,
        step_id: "echo",
        update: {
          input: [
            { path: "input.text", target: "text" },
            { target: "mode", value: { kind: "fast" } },
          ],
          retry: null,
          timeout_seconds: null,
        },
      }),
    ).toBe(
      "uv run wf draft update capability console.demo --revision 2 --step echo --clear-retry --clear-timeout --input input.text=text --value 'mode={\"kind\":\"fast\"}'",
    );
  });

  it("renders replacement binding clear flags and non-equivalent evidence", async () => {
    const { getOperationMeta } = await import("./method-registry.js");
    const input = getOperationMeta(
      "workflow.draft_workspaces.set_step_input_bindings",
    );
    const output = getOperationMeta(
      "workflow.draft_workspaces.set_step_output_bindings",
    );
    if (input === undefined || output === undefined) {
      throw new Error("missing focused binding operation");
    }

    expect(
      input.equivalentCli({
        workspace_id: "console.demo",
        revision: 3,
        step_id: "render",
        bindings: [],
      }),
    ).toBe("uv run wf draft set-input console.demo --revision 3 --step render --clear");
    expect(
      output.equivalentCli({
        workspace_id: "console.demo",
        revision: 4,
        step_id: "render",
        bindings: [],
      }),
    ).toBe("uv run wf draft set-output console.demo --revision 4 --step render --clear");
    expect(
      input.equivalentCli({
        workspace_id: "console.demo",
        revision: 3,
        step_id: "render",
        bindings: [
          {
            path: { root: "input", parts: ["title"] },
            target: "report.title",
          },
        ],
      }),
    ).toContain(
      "[non-equivalent: unavailable CLI representation for input_bindings (use --bindings-file)]",
    );
  });

  it("shell-quotes complete route and binding map assignments", async () => {
    const { getOperationMeta } = await import("./method-registry.js");
    const operation = getOperationMeta(
      "workflow.draft_workspaces.add_step_from_capability",
    );
    if (operation === undefined) throw new Error("missing add operation");

    expect(
      operation.equivalentCli({
        workspace_id: "console.demo",
        revision: 1,
        step_id: "echo",
        capability_name: "local.example.echo",
        routes: { "when done": "state path" },
        input_map: { "input value": "local target's" },
        bind_outputs: { "output value": "state target" },
      }),
    ).toBe(
      "uv run wf draft add capability console.demo --revision 1 --step echo --capability local.example.echo --route 'when done=state path' --input 'input value=local target''s' --bind-output 'output value=state target'",
    );
  });

  it("renders path and value input bindings for add", async () => {
    const { getOperationMeta } = await import("./method-registry.js");
    const operation = getOperationMeta(
      "workflow.draft_workspaces.add_step_from_capability",
    );
    if (operation === undefined) throw new Error("missing add operation");

    expect(
      operation.equivalentCli({
        workspace_id: "console.demo",
        revision: 1,
        step_id: "echo",
        capability_name: "local.example.echo",
        input_bindings: [
          { path: "state.text", target: "text" },
          { target: "mode", value: { kind: "fast" } },
        ],
      }),
    ).toBe(
      "uv run wf draft add capability console.demo --revision 1 --step echo --capability local.example.echo --input state.text=text --value 'mode={\"kind\":\"fast\"}'",
    );
  });

  it("explains unavailable inline schema and capability fields", async () => {
    const { getOperationMeta } = await import("./method-registry.js");
    const createEmpty = getOperationMeta(
      "workflow.draft_workspaces.create_empty",
    );
    const createFromCapability = getOperationMeta(
      "workflow.draft_workspaces.create_from_capability",
    );
    if (createEmpty === undefined || createFromCapability === undefined) {
      throw new Error("missing create operation");
    }

    const emptyCli = createEmpty.equivalentCli({
      workspace_id: "console.demo",
      name: "console.demo",
      input_schema: { type: "object" },
      state_schema: { type: "object" },
      output_schema: { type: "object" },
    });
    expect(emptyCli).toContain("uv run wf draft create console.demo --name console.demo");
    expect(emptyCli).toContain("non-equivalent");
    expect(emptyCli).toContain("input_schema");
    expect(emptyCli).toContain("state_schema");
    expect(emptyCli).toContain("output_schema");

    const fromCapabilityCli = createFromCapability.equivalentCli({
      workspace_id: "console.demo",
      capability_name: "local.example.echo",
      input_schema: { type: "object" },
      state_schema: { type: "object" },
      output_schema: { type: "object" },
      input: [{ path: "input.text", target: "text" }],
      output: [{ source: "text", target: "state.text" }],
      input_map: { "input.text": "text" },
      output_map: { text: "state.text" },
      error_message_source: "state.error",
    });
    expect(fromCapabilityCli).toContain("non-equivalent");
    for (const field of [
      "input_schema",
      "state_schema",
      "output_schema",
      "input",
      "output",
      "input_map",
      "output_map",
      "error_message_source",
    ]) {
      expect(fromCapabilityCli).toContain(field);
    }
  });

  it("explains structural bindings that require a bindings file", async () => {
    const { getOperationMeta } = await import("./method-registry.js");
    const operation = getOperationMeta(
      "workflow.draft_workspaces.add_step_from_capability",
    );
    if (operation === undefined) throw new Error("missing add operation");

    const cli = operation.equivalentCli({
      workspace_id: "console.demo",
      revision: 1,
      step_id: "echo",
      capability_name: "local.example.echo",
      input_bindings: [
        {
          path: { root: "state", parts: ["text"] },
          target: { root: "local", parts: ["text"] },
        },
      ],
    });

    expect(cli).toContain("non-equivalent");
    expect(cli).toContain("input_bindings");
    expect(cli).toContain("--bindings-file");
  });
});
