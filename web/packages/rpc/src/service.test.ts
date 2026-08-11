import { Effect, Either } from "effect";
import { describe, expect, it } from "vitest";
import {
  RpcDecodeError,
  RpcProtocolError,
  RpcRemoteError,
  UpstreamConnectionError,
  UpstreamResponseTooLargeError,
  UpstreamTimeoutError,
} from "./errors.js";
import {
  WorkflowRpc,
  makeWorkflowRpcLayer,
  type OperationExchange,
  type WorkflowRpcOptions,
} from "./service.js";
import type { OperationName } from "./method-registry.js";

type JsonRpcRequest = {
  readonly jsonrpc: "2.0";
  readonly id: number | string;
  readonly method: string;
  readonly params: unknown;
};

const bodyText = async (
  body: RequestInit["body"] | null | undefined,
): Promise<string> => {
  if (typeof body === "string") return body;
  if (body instanceof Uint8Array) return new TextDecoder().decode(body);
  if (body instanceof Blob) return body.text();
  if (body instanceof ReadableStream) return new Response(body).text();
  throw new Error("expected JSON-RPC request body");
};

const requestBody = async (
  input: Parameters<typeof globalThis.fetch>[0],
  init?: RequestInit,
): Promise<JsonRpcRequest> => {
  if (input instanceof Request) {
    return JSON.parse(await input.clone().text()) as JsonRpcRequest;
  }

  return JSON.parse(await bodyText(init?.body ?? null)) as JsonRpcRequest;
};

const jsonResponse = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });

const runOperation = (
  options: WorkflowRpcOptions,
  operation: OperationName = "workflow.health",
  params: unknown = {},
): Promise<OperationExchange> =>
  Effect.gen(function* () {
    const rpc = yield* WorkflowRpc;
    return yield* rpc.execute(
      operation,
      "http://127.0.0.1:8765/rpc",
      params,
    );
  }).pipe(Effect.provide(makeWorkflowRpcLayer(options)), Effect.runPromise);

const runEither = (
  options: WorkflowRpcOptions,
): Promise<Either.Either<OperationExchange, unknown>> =>
  Effect.gen(function* () {
    const rpc = yield* WorkflowRpc;
    return yield* rpc
      .execute("workflow.health", "http://127.0.0.1:8765/rpc", {})
      .pipe(Effect.either);
  }).pipe(Effect.provide(makeWorkflowRpcLayer(options)), Effect.runPromise);

const draftWorkspaceResult = {
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
    routes: { echo: { ok: "__end__" } },
  },
};

const createFromCapabilityResult = {
  ...draftWorkspaceResult,
  next_actions: {
    can_continue: false,
    can_save_now: true,
    recommended_next_tool: "workflow.draft_workspaces.validate",
    reason: "draft is ready for validation",
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
};

const lifecycleCases = [
  {
    operation: "workflow.capabilities.list" as const,
    params: { query: "document", source_id: "local.lda_docs", limit: 25 },
    result: {
      capabilities: [
        {
          kind: "node_spec",
          name: "local.lda_docs.read_documents",
          source_id: "local.lda_docs",
          description: "Read selected project documents.",
          outcomes: ["ok", "error"],
          is_async: false,
          input_fields: ["names"],
          output_fields: ["documents"],
        },
      ],
      next_cursor: null,
      total: 1,
    },
  },
  {
    operation: "workflow.capabilities.inspect" as const,
    params: { qualified_name: "local.lda_docs.read_documents" },
    result: {
      kind: "node_spec",
      name: "local.lda_docs.read_documents",
      source_id: "local.lda_docs",
      description: "Read selected project documents.",
      is_async: false,
      accepts_context: false,
      outcomes: ["ok", "error"],
      input_schema: { type: "object", properties: { names: { type: "array" } } },
      output_schema: { type: "object", properties: { documents: { type: "array" } } },
      wrapper_hints: {
        capability_name: "local.lda_docs.read_documents",
        confidence: "high",
        declared_outcomes: ["ok", "error"],
        input_map: { names: "input.names" },
        input_schema: { type: "object" },
        missing_decisions: [],
        notes: [],
        outcome_candidates: [],
        outcome_policy: "preserve_declared",
        output_map: { documents: "output.documents" },
        output_schema: { type: "object" },
        state_schema: { type: "object" },
        suggested_wrapper_outcomes: ["ok", "error"],
      },
    },
  },
  {
    operation: "workflow.draft_workspaces.list" as const,
    params: {},
    result: {
      workspaces: [
        {
          workspace_id: "console.demo",
          revision: 1,
          title: "Console demo",
          status: "valid",
          diagnostics: [],
          summary: {
            name: "console.demo",
            start: "read",
            step_count: 1,
            route_count: 1,
            steps: ["read"],
          },
        },
      ],
    },
  },
  {
    operation: "workflow.draft_workspaces.get" as const,
    params: { workspace_id: "console.demo", include_draft: true },
    result: {
      workspace_id: "console.demo",
      revision: 1,
      title: "Console demo",
      status: "valid",
      diagnostics: [],
      summary: {
        name: "console.demo",
        start: "read",
        step_count: 1,
        route_count: 1,
        steps: ["read"],
      },
      draft: {
        name: "console.demo",
        start: "read",
        steps: { read: { use: "local.lda_docs.read_documents" } },
        routes: { read: { ok: "__end__" } },
      },
    },
  },
  {
    operation: "workflow.draft_workspaces.create_empty" as const,
    params: {
      workspace_id: "console.demo",
      name: "console.demo",
      title: "Console demo",
      outcomes: ["ok"],
    },
    result: draftWorkspaceResult,
  },
  {
    operation: "workflow.draft_workspaces.create_from_capability" as const,
    params: {
      workspace_id: "console.demo",
      capability_name: "local.example.echo",
      name: "console.demo",
      input_map: { text: "input.text" },
      output_map: { text: "state.text" },
    },
    result: createFromCapabilityResult,
  },
  {
    operation: "workflow.draft_workspaces.add_step_from_capability" as const,
    params: {
      workspace_id: "console.demo",
      revision: 1,
      step_id: "echo",
      capability_name: "local.example.echo",
      route_from_step: null,
      route_from_outcome: "ok",
      routes: { ok: "__end__" },
      input_map: { text: "input.text" },
      bind_outputs: { text: "state.text" },
      retry: 1,
      timeout_seconds: 30,
    },
    result: draftWorkspaceResult,
  },
  {
    operation: "workflow.draft_workspaces.update_capability_step" as const,
    params: {
      workspace_id: "console.demo",
      revision: 2,
      step_id: "echo",
      update: { desc: "Echo text", retry: 2, timeout_seconds: 45 },
    },
    result: draftWorkspaceResult,
  },
  {
    operation: "workflow.draft_workspaces.set_route" as const,
    params: {
      workspace_id: "console.demo",
      revision: 2,
      step_id: "echo",
      outcome: "ok",
      target: "__end__",
    },
    result: draftWorkspaceResult,
  },
  {
    operation: "workflow.draft_workspaces.set_step_input_bindings" as const,
    params: {
      workspace_id: "console.demo",
      revision: 3,
      step_id: "render",
      bindings: [
        { path: "input.title", target: "report.title" },
        { target: "format", value: "markdown" },
      ],
    },
    result: draftWorkspaceResult,
  },
  {
    operation: "workflow.draft_workspaces.set_step_output_bindings" as const,
    params: {
      workspace_id: "console.demo",
      revision: 4,
      step_id: "render",
      bindings: [{ source: "report", target: "state.report" }],
    },
    result: draftWorkspaceResult,
  },
  {
    operation: "workflow.draft_workspaces.validate" as const,
    params: { workspace_id: "console.demo" },
    result: draftWorkspaceResult,
  },
  {
    operation: "workflow.artifacts.list" as const,
    params: { limit: 50 },
    result: {
      nodes: [
        {
          name: "workflow.report@1",
          artifact_id: "report",
          version: 1,
          kind: "workflow",
          display_name: "Report",
          description: null,
          outcomes: ["ok"],
          input_schema: { type: "object" },
          output_schema: { type: "object" },
          required_sources: ["local.report"],
          diagnostics: [],
        },
      ],
      total: 1,
      next_cursor: null,
      limit: 50,
    },
  },
  {
    operation: "workflow.artifacts.inspect" as const,
    params: { artifact_id: "report", version: 1 },
    result: {
      id: "report",
      version: 1,
      title: "Report",
      kind: "workflow",
      description: null,
      outcomes: ["ok"],
      input_schema: { type: "object" },
      output_schema: { type: "object" },
      plan: { nodes: [], edges: [] },
      required_capabilities: [],
      workflow_dependencies: {},
      created_from_catalog_version: null,
    },
  },
  {
    operation: "workflow.deployments.list" as const,
    params: {},
    result: {
      deployments: [
        {
          id: "report.default",
          artifact_id: "report",
          artifact_version: 1,
          binding_count: 1,
          drift_policy: "block",
        },
      ],
    },
  },
  {
    operation: "workflow.deployments.inspect" as const,
    params: { deployment_id: "report.default" },
    result: {
      id: "report.default",
      artifact_id: "report",
      artifact_version: 1,
      bindings: [{ logical_source: "local.report", concrete_source: "report" }],
      drift_policy: "block",
    },
  },
  {
    operation: "workflow.deployments.validate" as const,
    params: { deployment_id: "report.default" },
    result: {
      deployment_id: "report.default",
      artifact_id: "report",
      artifact_version: 1,
      status: "runnable",
      diagnostics: [],
      next_actions: {
        can_continue: true,
        can_save_now: null,
        recommended_next_tool: null,
        reason: "deployment is valid",
        patch_examples: [],
        warnings: [],
      },
    },
  },
  {
    operation: "workflow.runs.list" as const,
    params: { limit: 50 },
    result: {
      runs: [
        {
          run_id: "run_1",
          deployment_id: "report.default",
          artifact_id: "report",
          artifact_version: 1,
          status: "interrupted",
          resume_readiness: "ready",
          diagnostic_count: 0,
          created_at: "2026-07-02T00:00:00Z",
          updated_at: "2026-07-02T00:00:01Z",
        },
      ],
      total: 1,
      cursor: null,
      next_cursor: null,
      limit: 50,
    },
  },
  {
    operation: "workflow.runs.inspect" as const,
    params: { run_id: "run_1" },
    result: {
      run_id: "run_1",
      deployment_id: "report.default",
      artifact_id: "report",
      artifact_version: 1,
      status: "interrupted",
      resume_readiness: "ready",
      interrupt: {
        id: "interrupt_1",
        frame_id: "frame_1",
        node_id: "review",
        kind: "review",
        payload: {},
        resumable: true,
        route: null,
        outcomes: [],
        request_schema: { type: "object" },
        resume_schema: { type: "object" },
        typed: true,
      },
      outcome: null,
      error: null,
      output: null,
      diagnostics: [],
      trace_count: 0,
      next_actions: {
        can_continue: false,
        can_save_now: null,
        recommended_next_tool: null,
        reason: "run is interrupted",
        patch_examples: [],
        warnings: [],
      },
    },
  },
  {
    operation: "workflow.runs.start" as const,
    params: {
      deployment_id: "lda_report_case_study.default",
      workflow_input: {
        selected_documents: [
          "project-brief.md",
          "architecture-notes.md",
          "evaluation-findings.md",
          "risk-register.md",
          "roadmap.md",
        ],
        board_path: "issue-board.json",
      },
      trace_range: { start: 0, limit: 50 },
    },
    result: {
      run_id: "run_demo",
      deployment_id: "lda_report_case_study.default",
      artifact_id: "lda_report_case_study",
      artifact_version: 1,
      status: "interrupted",
      resume_readiness: "ready",
      interrupt: {
        id: "interrupt_demo",
        frame_id: "frame_review",
        node_id: "review_issues",
        kind: "issue_review",
        payload: {
          report_markdown: "# lda.chat Thesis And Project Readiness Report",
          proposed_issues: [
            {
              id: "demo-issue-1",
              title: "Prepare demo script",
              body: "Write the defense walkthrough.",
              severity: "medium",
            },
          ],
        },
        resumable: true,
        route: null,
        outcomes: ["submitted", "cancelled"],
        request_schema: {
          type: "object",
          required: ["report_markdown", "proposed_issues"],
        },
        resume_schema: {
          type: "object",
          required: ["approved", "selected_issue_ids"],
        },
        typed: true,
      },
      outcome: null,
      error: null,
      output: null,
      diagnostics: [],
      trace_count: 1,
      next_actions: {
        can_continue: true,
        can_save_now: null,
        recommended_next_tool: "wf.workflow.resume_run",
        reason: "run is interrupted",
        patch_examples: [],
        warnings: [],
      },
    },
  },
  {
    operation: "workflow.runs.resume" as const,
    params: {
      run_id: "run_demo",
      resume_payload: {
        approved: true,
        selected_issue_ids: ["demo-issue-1"],
        comment: "Create selected issues.",
      },
      resume_outcome: "submitted",
      trace_range: { start: 0, limit: 50 },
    },
    result: {
      run_id: "run_demo",
      deployment_id: "lda_report_case_study.default",
      artifact_id: "lda_report_case_study",
      artifact_version: 1,
      status: "completed",
      resume_readiness: "not_applicable",
      interrupt: null,
      outcome: "completed",
      error: null,
      output: {
        approved: true,
        markdown: "# lda.chat Thesis And Project Readiness Report",
        created_issues: [
          {
            id: "ISSUE-001",
            title: "Prepare demo script",
            url: "local://issues/ISSUE-001",
          },
        ],
        selected_issue_ids: ["demo-issue-1"],
        comment: "Create selected issues.",
      },
      diagnostics: [],
      trace_count: 4,
      next_actions: {
        can_continue: false,
        can_save_now: null,
        recommended_next_tool: null,
        reason: "Run completed.",
        patch_examples: [],
        warnings: [],
      },
    },
  },
  {
    operation: "workflow.runs.trace" as const,
    params: { run_id: "run_1", trace_range: { start: 0, limit: 50 } },
    result: {
      run_id: "run_1",
      deployment_id: "report.default",
      artifact_id: "report",
      artifact_version: 1,
      status: "interrupted",
      resume_readiness: "ready",
      interrupt: {
        id: "interrupt_1",
        frame_id: "frame_1",
        node_id: "review",
        kind: "review",
        payload: {},
        resumable: true,
        route: null,
        outcomes: ["submitted", "cancelled"],
        request_schema: { type: "object" },
        resume_schema: { type: "object" },
        typed: true,
      },
      outcome: null,
      error: null,
      output: null,
      diagnostics: [],
      trace_count: 1,
      next_actions: {
        can_continue: true,
        can_save_now: null,
        recommended_next_tool: "wf.workflow.resume_run",
        reason: "run is interrupted",
        patch_examples: [],
        warnings: [],
      },
      trace_start: 0,
      trace_limit: 50,
      trace_truncated: false,
      trace: [
        {
          frame_id: "frame_1",
          node_id: "review",
          step_type: "interrupt",
          resolved_input: { report: "..." },
          outcome: "submitted",
          output: {},
          state_changes: {},
          next_node_id: "create_issues",
        },
      ],
    },
  },
] as const;

describe("WorkflowRpc", () => {
  it("uses @effect/rpc and returns exact raw request and response evidence", async () => {
    const fetch: typeof globalThis.fetch = async (input, init) => {
      const request = await requestBody(input, init);
      return jsonResponse({
        jsonrpc: "2.0",
        id: request.id,
        result: { status: "ok", store_root: "C:/store" },
      });
    };

    const exchange = await runOperation({ fetch });

    expect(exchange.target).toBe("http://127.0.0.1:8765/rpc");
    expect(exchange.interpreted).toEqual({
      status: "ok",
      storeRoot: "C:/store",
    });
    expect(exchange.exchange.request).toMatchObject({
      jsonrpc: "2.0",
      method: "workflow.health",
      params: {},
    });
    expect(exchange.exchange.response).toMatchObject({
      jsonrpc: "2.0",
      result: { status: "ok", store_root: "C:/store" },
    });
  });

  it("requests manual redirect handling", async () => {
    let redirect: RequestInit["redirect"];
    const fetch: typeof globalThis.fetch = async (input, init) => {
      redirect = init?.redirect ?? (input instanceof Request ? input.redirect : undefined);
      const request = await requestBody(input, init);
      return jsonResponse({
        jsonrpc: "2.0",
        id: request.id,
        result: { status: "ok", store_root: "C:/store" },
      });
    };

    await runOperation({ fetch });

    expect(redirect).toBe("manual");
  });

  it("maps a standard foreign JSON-RPC error and preserves evidence", async () => {
    const fetch: typeof globalThis.fetch = async (input, init) => {
      const request = await requestBody(input, init);
      return jsonResponse({
        jsonrpc: "2.0",
        id: request.id,
        error: { code: -32602, message: "Invalid params", data: { field: "x" } },
      });
    };

    const result = await runEither({ fetch });

    expect(Either.isLeft(result)).toBe(true);
    if (Either.isRight(result)) return;
    expect(result.left).toBeInstanceOf(RpcRemoteError);
    expect((result.left as RpcRemoteError).exchange?.response).toMatchObject({
      error: { code: -32602, message: "Invalid params" },
    });
  });

  it("maps malformed successful results to decode errors with evidence", async () => {
    const fetch: typeof globalThis.fetch = async (input, init) => {
      const request = await requestBody(input, init);
      return jsonResponse({
        jsonrpc: "2.0",
        id: request.id,
        result: { status: "wrong", store_root: "C:/store" },
      });
    };

    const result = await runEither({ fetch });

    expect(Either.isLeft(result)).toBe(true);
    if (Either.isRight(result)) return;
    expect(result.left).toBeInstanceOf(RpcDecodeError);
    expect((result.left as RpcDecodeError).exchange?.response).toMatchObject({
      result: { status: "wrong", store_root: "C:/store" },
    });
  });

  it("decodes the canonical expanded source list result", async () => {
    const fetch: typeof globalThis.fetch = async (input, init) => {
      const request = await requestBody(input, init);
      return jsonResponse({
        jsonrpc: "2.0",
        id: request.id,
        result: {
          sources: [
            {
              id: "local.demo",
              kind: "python",
              enabled: true,
              visibility: {
                planner: true,
                client: true,
                admin_dashboard: true,
              },
              permissions: {
                safe_for_workflow: true,
                calls_upstream: false,
                mutates_config: false,
                mutates_auth: false,
              },
              policy: { platform: false, binding_required: true },
              description: "Local demo source",
              tool_count: 1,
              node_spec_count: 0,
              reducer_count: 0,
              prompt_count: 0,
              resource_count: 0,
              preview: {
                tools: ["generate"],
                node_specs: [],
                reducers: [],
                prompts: [],
                resources: [],
              },
              has_more: {
                tools: false,
                node_specs: false,
                reducers: false,
                prompts: false,
                resources: false,
              },
            },
          ],
          next_cursor: null,
          total: 1,
        },
      });
    };

    const exchange = await runOperation(
      { fetch },
      "workflow.sources.list",
      { limit: 50 },
    );

    expect(exchange.interpreted).toMatchObject({
      total: 1,
      sources: [{ id: "local.demo", counts: { tools: 1 } }],
    });
  });

  it("rejects invalid source count shapes as decode errors", async () => {
    const fetch: typeof globalThis.fetch = async (input, init) => {
      const request = await requestBody(input, init);
      return jsonResponse({
        jsonrpc: "2.0",
        id: request.id,
        result: {
          sources: [
            {
              id: "local.demo",
              kind: "python",
              enabled: true,
              description: null,
              tool_count: -1,
              node_spec_count: 0,
              reducer_count: 0,
              prompt_count: 0,
              resource_count: 0,
            },
          ],
          next_cursor: null,
          total: 1,
        },
      });
    };

    const result = await Effect.gen(function* () {
      const rpc = yield* WorkflowRpc;
      return yield* rpc
        .execute(
          "workflow.sources.list",
          "http://127.0.0.1:8765/rpc",
          {},
        )
        .pipe(Effect.either);
    }).pipe(Effect.provide(makeWorkflowRpcLayer({ fetch })), Effect.runPromise);

    expect(Either.isLeft(result)).toBe(true);
    if (Either.isRight(result)) return;
    expect(result.left).toBeInstanceOf(RpcDecodeError);
  });

  it("fails with a bounded timeout", async () => {
    const fetch: typeof globalThis.fetch = () => new Promise<Response>(() => {});

    const result = await runEither({ fetch, timeoutMilliseconds: 5 });

    expect(Either.isLeft(result)).toBe(true);
    if (Either.isRight(result)) return;
    expect(result.left).toBeInstanceOf(UpstreamTimeoutError);
  });

  it("maps transport failures to upstream connection errors", async () => {
    const fetch: typeof globalThis.fetch = async () => {
      throw new Error("connection refused");
    };

    const result = await runEither({ fetch });

    expect(Either.isLeft(result)).toBe(true);
    if (Either.isRight(result)) return;
    expect(result.left).toBeInstanceOf(UpstreamConnectionError);
  });

  it("rejects a response larger than the configured byte limit", async () => {
    const fetch: typeof globalThis.fetch = async (input, init) => {
      const request = await requestBody(input, init);
      return jsonResponse({
        jsonrpc: "2.0",
        id: request.id,
        result: { status: "ok", store_root: "x".repeat(512) },
      });
    };

    const result = await runEither({ fetch, maxResponseBytes: 128 });

    expect(Either.isLeft(result)).toBe(true);
    if (Either.isRight(result)) return;
    expect(result.left).toBeInstanceOf(UpstreamResponseTooLargeError);
  });

  it("rejects a redirect response instead of decoding it", async () => {
    const fetch: typeof globalThis.fetch = async () =>
      new Response("", { status: 302, headers: { location: "/elsewhere" } });

    const result = await runEither({ fetch });

    expect(Either.isLeft(result)).toBe(true);
    if (Either.isRight(result)) return;
    expect(result.left).toBeInstanceOf(RpcProtocolError);
  });
});

describe("lifecycle operations", () => {
  for (const testCase of lifecycleCases) {
    it(`handles ${testCase.operation} successfully`, async () => {
      const fetch: typeof globalThis.fetch = async (input, init) => {
        const request = await requestBody(input, init);
        expect(request.method).toBe(testCase.operation);
        expect(request.params).toEqual(testCase.params);
        return jsonResponse({
          jsonrpc: "2.0",
          id: request.id,
          result: testCase.result,
        });
      };

      const exchange = await runOperation(
        { fetch },
        testCase.operation,
        testCase.params,
      );

      expect(exchange.operation).toBe(testCase.operation);
      expect(exchange.interpreted).toBeDefined();
    });
  }

  it("interprets run trace frames with the console lifecycle shape", async () => {
    const traceCase = lifecycleCases.find(
      (testCase) => testCase.operation === "workflow.runs.trace",
    );
    expect(traceCase).toBeDefined();
    if (!traceCase) return;

    const fetch: typeof globalThis.fetch = async (input, init) => {
      const request = await requestBody(input, init);
      return jsonResponse({
        jsonrpc: "2.0",
        id: request.id,
        result: traceCase.result,
      });
    };

    const exchange = await runOperation(
      { fetch },
      traceCase.operation,
      traceCase.params,
    );

    expect(exchange.interpreted).toMatchObject({
      frames: [
        {
          frameId: "frame_1",
          nodeId: "review",
          stepType: "interrupt",
          outcome: "submitted",
          nextNodeId: "create_issues",
        },
      ],
      traceStart: 0,
      traceLimit: 50,
      traceTruncated: false,
    });
    expect(exchange.interpreted).not.toHaveProperty("trace");
  });

  it("omits absent optional trace-range flags from the equivalent CLI", async () => {
    const traceCase = lifecycleCases.find(
      (testCase) => testCase.operation === "workflow.runs.trace",
    );
    expect(traceCase).toBeDefined();
    if (!traceCase) return;

    const fetch: typeof globalThis.fetch = async (input, init) => {
      const request = await requestBody(input, init);
      return jsonResponse({
        jsonrpc: "2.0",
        id: request.id,
        result: traceCase.result,
      });
    };

    const exchange = await runOperation(
      { fetch },
      "workflow.runs.trace",
      { run_id: "run_1", trace_range: {} },
    );

    expect(exchange.equivalentCli).toBe("uv run wf run trace run_1");
  });

  it("interprets typed interrupt contracts from run start", async () => {
    const startCase = lifecycleCases.find(
      (testCase) => testCase.operation === "workflow.runs.start",
    );
    expect(startCase).toBeDefined();
    if (!startCase) return;

    const fetch: typeof globalThis.fetch = async (input, init) => {
      const request = await requestBody(input, init);
      return jsonResponse({
        jsonrpc: "2.0",
        id: request.id,
        result: startCase.result,
      });
    };

    const exchange = await runOperation(
      { fetch },
      startCase.operation,
      startCase.params,
    );

    expect(exchange.interpreted).toMatchObject({
      runId: "run_demo",
      status: "interrupted",
      interrupt: {
        kind: "issue_review",
        typed: true,
        outcomes: ["submitted", "cancelled"],
      },
      nextActions: {
        canContinue: true,
      },
    });
  });
});

describe("capability call", () => {
  it("rejects malformed payloads before fetching", async () => {
    let fetchCalled = false;
    const fetch: typeof globalThis.fetch = async () => {
      fetchCalled = true;
      throw new Error("fetch must not be called");
    };

    const result = await Effect.gen(function* () {
      const rpc = yield* WorkflowRpc;
      return yield* rpc
        .execute(
          "workflow.capabilities.call",
          "http://127.0.0.1:8765/rpc",
          { qualified_name: "" },
        )
        .pipe(Effect.either);
    }).pipe(Effect.provide(makeWorkflowRpcLayer({ fetch })), Effect.runPromise);

    expect(Either.isLeft(result)).toBe(true);
    if (Either.isRight(result)) return;
    expect(result.left).toBeInstanceOf(RpcDecodeError);
    expect(fetchCalled).toBe(false);
  });

  it("dispatches the exact method and interprets the result", async () => {
    const params = {
      qualified_name: "local.example.echo",
      payload: { text: "hello" },
      deployment_id: "demo.default",
    };
    const result = {
      qualified_name: "local.example.echo",
      source_id: "local.example",
      kind: "node_spec" as const,
      deployment_id: "demo.default",
      outcome: "ok",
      output: { text: "hello" },
      diagnostics: [
        {
          bound_source: "local.example",
          code: "ok",
          logical_ref: "local.example.echo",
          message: "called",
          repair_hint: null,
          severity: "info",
        },
      ],
    };
    const fetch: typeof globalThis.fetch = async (input, init) => {
      const request = await requestBody(input, init);
      expect(request.method).toBe("workflow.capabilities.call");
      expect(request.params).toEqual(params);
      return jsonResponse({
        jsonrpc: "2.0",
        id: request.id,
        result,
      });
    };

    const exchange = await runOperation(
      { fetch },
      "workflow.capabilities.call",
      params,
    );

    expect(exchange.interpreted).toEqual({
      qualifiedName: "local.example.echo",
      sourceId: "local.example",
      kind: "node_spec",
      deploymentId: "demo.default",
      outcome: "ok",
      output: { text: "hello" },
      diagnostics: [
        {
          boundSource: "local.example",
          code: "ok",
          logicalRef: "local.example.echo",
          message: "called",
          repairHint: null,
          severity: "info",
        },
      ],
    });
    expect(exchange.equivalentCli).toBe(
      "uv run wf cap call local.example.echo --input '{\"text\":\"hello\"}' --deployment demo.default",
    );
  });
});
