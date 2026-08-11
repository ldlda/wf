import { describe, it, expect, vi } from "vitest";
import { upgradeWebSocket } from "@hono/node-server";
import { createApp, type RunOperation } from "./app.js";
import { createBrowserOperationPolicy } from "./browser-operation-policy.js";
import { createPresentationRoomService } from "./presentation-sync/rooms.js";
import type { OperationExchange } from "@lda/workflow-rpc";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";

const makeExchange = (
  overrides: Partial<OperationExchange> = {},
): OperationExchange => ({
  operation: "workflow.health",
  target: "http://127.0.0.1:8765/rpc",
  label: "Health check",
  interpreted: { status: "ok", storeRoot: "/tmp/store" },
  exchange: { request: {}, response: { status: "ok" } },
  equivalentCli: "uv run wf status",
  durationMs: 12,
  ...overrides,
});

const okRunner: RunOperation = vi.fn(async (operation) =>
  makeExchange({ operation, target: "http://127.0.0.1:8765/rpc" }),
);

const failRunner =
  (code: string, message: string): RunOperation =>
  async () => {
    throw Object.assign(new Error(message), {
      _tag: code,
      exchange: { request: { method: "x" }, response: { error: message } },
    });
  };

type AppDependencies = Parameters<typeof createApp>[0];

const disabledBrowserOperationPolicy = createBrowserOperationPolicy({
  enableCapabilityCalls: false,
});

const makeApp = (
  dependencies: Omit<AppDependencies, "presentationSync" | "browserOperationPolicy"> &
    Partial<Pick<AppDependencies, "browserOperationPolicy">>,
) =>
  createApp({
    ...dependencies,
    browserOperationPolicy:
      dependencies.browserOperationPolicy ?? disabledBrowserOperationPolicy,
    presentationSync: {
      rooms: createPresentationRoomService(),
      upgradeWebSocket,
    },
  });

const app = makeApp({ runOperation: okRunner });

const validConsoleHeaders = {
  "content-type": "application/json",
  "x-workflow-console": "1",
} as const;

describe("GET /api/health", () => {
  it("returns 200 with ok status", async () => {
    const res = await app.request("/api/health");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body).toEqual({ ok: true, status: "ok" });
  });
});

describe("POST /api/connect", () => {
  it("calls workflow.health and returns connected DTO", async () => {
    const res = await app.request("/api/connect", {
      method: "POST",
      headers: validConsoleHeaders,
      body: JSON.stringify({ target: "http://127.0.0.1:8000/rpc" }),
    });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.ok).toBe(true);
    expect(body.connection.status).toBe("connected");
    expect(body.connection.target).toBe("http://127.0.0.1:8765/rpc");
    expect(body.connection.serverStatus).toBe("ok");
    expect(body.connection.storeRoot).toBe("/tmp/store");
    expect(okRunner).toHaveBeenCalledWith(
      "workflow.health",
      "http://127.0.0.1:8000/rpc",
      {},
    );
  });

  it("returns 400 when target is missing", async () => {
    const res = await app.request("/api/connect", {
      method: "POST",
      headers: validConsoleHeaders,
      body: JSON.stringify({}),
    });
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.ok).toBe(false);
    expect(body.error.code).toBe("invalid_target");
  });

  it("returns a decode error when health interpretation is malformed", async () => {
    const malformedApp = makeApp({
      runOperation: async () => makeExchange({ interpreted: { status: "ok" } }),
    });
    const res = await malformedApp.request("/api/connect", {
      method: "POST",
      headers: validConsoleHeaders,
      body: JSON.stringify({ target: "http://127.0.0.1:8000/rpc" }),
    });
    expect(res.status).toBe(502);
    const body = await res.json();
    expect(body.ok).toBe(false);
    expect(body.error.code).toBe("rpc_decode_error");
  });
});

describe("console POST request boundary", () => {
  const routes = [
    {
      path: "/api/connect",
      body: { target: "http://127.0.0.1:8000/rpc" },
    },
    {
      path: "/api/rpc",
      body: {
        operation: "workflow.health",
        target: "http://127.0.0.1:8000/rpc",
        params: {},
      },
    },
  ] as const;

  it.each(routes)("rejects text/plain at $path before invoking the runner", async ({
    path: requestPath,
    body,
  }) => {
    const runOperation = vi.fn<RunOperation>(async (operation) =>
      makeExchange({ operation }),
    );
    const guardedApp = makeApp({ runOperation });

    const res = await guardedApp.request(requestPath, {
      method: "POST",
      headers: {
        "content-type": "text/plain",
        "x-workflow-console": "1",
      },
      body: JSON.stringify(body),
    });

    expect(res.status).toBe(415);
    expect(runOperation).not.toHaveBeenCalled();
  });

  it.each(routes)("rejects a missing console header at $path before invoking the runner", async ({
    path: requestPath,
    body,
  }) => {
    const runOperation = vi.fn<RunOperation>(async (operation) =>
      makeExchange({ operation }),
    );
    const guardedApp = makeApp({ runOperation });

    const res = await guardedApp.request(requestPath, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });

    expect(res.status).toBe(403);
    expect(runOperation).not.toHaveBeenCalled();
  });

  it.each([
    {
      label: "foreign Origin",
      headers: { ...validConsoleHeaders, origin: "https://foreign.example" },
    },
    {
      label: "foreign Sec-Fetch-Site",
      headers: { ...validConsoleHeaders, "sec-fetch-site": "cross-site" },
    },
  ])("rejects $label before either runner is invoked", async ({ headers }) => {
    const runOperation = vi.fn<RunOperation>(async (operation) =>
      makeExchange({ operation }),
    );
    const guardedApp = makeApp({ runOperation });

    for (const route of routes) {
      const res = await guardedApp.request(route.path, {
        method: "POST",
        headers,
        body: JSON.stringify(route.body),
      });
      expect(res.status).toBe(403);
    }

    expect(runOperation).not.toHaveBeenCalled();
  });

  it.each(routes)("allows a same-origin console request through $path", async ({
    path: requestPath,
    body,
  }) => {
    const runOperation = vi.fn<RunOperation>(async (operation) =>
      makeExchange({ operation }),
    );
    const guardedApp = makeApp({ runOperation });

    const res = await guardedApp.request(`http://localhost:5173${requestPath}`, {
      method: "POST",
      headers: {
        ...validConsoleHeaders,
        origin: "http://localhost:5173",
        "sec-fetch-site": "same-origin",
      },
      body: JSON.stringify(body),
    });

    expect(res.status).toBe(200);
    expect(runOperation).toHaveBeenCalledTimes(1);
  });
});

describe("POST /api/rpc", () => {
  it.each([
    { operation: "workflow.capabilities.list", params: {} },
    {
      operation: "workflow.capabilities.inspect",
      params: { qualified_name: "workflow.health" },
    },
    { operation: "workflow.draft_workspaces.list", params: {} },
    {
      operation: "workflow.draft_workspaces.get",
      params: { workspace_id: "draft-1" },
    },
    {
      operation: "workflow.draft_workspaces.create_empty",
      params: { workspace_id: "draft-1", name: "draft.workflow" },
    },
    {
      operation: "workflow.draft_workspaces.create_from_capability",
      params: {
        workspace_id: "draft-1",
        capability_name: "local.example.echo",
      },
    },
    {
      operation: "workflow.draft_workspaces.add_step_from_capability",
      params: {
        workspace_id: "draft-1",
        revision: 1,
        step_id: "echo",
        capability_name: "local.example.echo",
      },
    },
    {
      operation: "workflow.draft_workspaces.update_capability_step",
      params: {
        workspace_id: "draft-1",
        revision: 1,
        step_id: "echo",
        update: { retry: 2 },
      },
    },
    {
      operation: "workflow.draft_workspaces.set_route",
      params: {
        workspace_id: "draft-1",
        revision: 1,
        step_id: "echo",
        outcome: "ok",
        target: "__end__",
      },
    },
    {
      operation: "workflow.draft_workspaces.set_step_input_bindings",
      params: {
        workspace_id: "draft-1",
        revision: 1,
        step_id: "echo",
        bindings: [{ target: "format", value: "markdown" }],
      },
    },
    {
      operation: "workflow.draft_workspaces.set_step_output_bindings",
      params: {
        workspace_id: "draft-1",
        revision: 1,
        step_id: "echo",
        bindings: [{ source: "result", target: "state.result" }],
      },
    },
    {
      operation: "workflow.draft_workspaces.validate",
      params: { workspace_id: "draft-1" },
    },
    { operation: "workflow.runs.start", params: {} },
    { operation: "workflow.runs.resume", params: {} },
  ] as const)("authorizes the allowlisted operation $operation", async ({
    operation,
    params,
  }) => {
    const res = await app.request("/api/rpc", {
      method: "POST",
      headers: validConsoleHeaders,
      body: JSON.stringify({
        operation,
        target: "http://127.0.0.1:8000/rpc",
        params,
      }),
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.ok).toBe(true);
    expect(body.operation).toBe(operation);
    expect(okRunner).toHaveBeenCalledWith(
      operation,
      "http://127.0.0.1:8000/rpc",
      params,
    );
  });

  it("invokes the requested operation", async () => {
    const res = await app.request("/api/rpc", {
      method: "POST",
      headers: validConsoleHeaders,
      body: JSON.stringify({
        operation: "workflow.sources.list",
        target: "http://127.0.0.1:8000/rpc",
        params: { limit: 10 },
      }),
    });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.ok).toBe(true);
    expect(body.operation).toBe("workflow.sources.list");
  });

  it("returns a distinct 403 when capability calls are disabled", async () => {
    const runOperation = vi.fn<RunOperation>();
    const disabledApp = makeApp({ runOperation });
    const res = await disabledApp.request("/api/rpc", {
      method: "POST",
      headers: validConsoleHeaders,
      body: JSON.stringify({
        operation: "workflow.capabilities.call",
        target: "http://127.0.0.1:8000/rpc",
        params: { capability_name: "local.example.echo", input: {} },
      }),
    });

    expect(res.status).toBe(403);
    expect(await res.json()).toEqual({
      ok: false,
      error: {
        code: "operation_disabled",
        message:
          "workflow.capabilities.call is disabled for this console server",
      },
      exchange: { request: null, response: null },
    });
    expect(runOperation).not.toHaveBeenCalled();
  });

  it("invokes capability calls when the injected policy enables them", async () => {
    const runOperation: RunOperation = vi.fn(async (operation) =>
      makeExchange({ operation }),
    );
    const enabledApp = makeApp({
      runOperation,
      browserOperationPolicy: createBrowserOperationPolicy({
        enableCapabilityCalls: true,
      }),
    });
    const params = { capability_name: "local.example.echo", input: {} };
    const res = await enabledApp.request("/api/rpc", {
      method: "POST",
      headers: validConsoleHeaders,
      body: JSON.stringify({
        operation: "workflow.capabilities.call",
        target: "http://127.0.0.1:8000/rpc",
        params,
      }),
    });

    expect(res.status).toBe(200);
    expect(runOperation).toHaveBeenCalledWith(
      "workflow.capabilities.call",
      "http://127.0.0.1:8000/rpc",
      params,
    );
  });

  it("returns 400 for unknown operation", async () => {
    const runOperation = vi.fn<RunOperation>();
    const rejectedApp = makeApp({ runOperation });
    const res = await rejectedApp.request("/api/rpc", {
      method: "POST",
      headers: validConsoleHeaders,
      body: JSON.stringify({
        operation: "foo.bar",
        target: "http://127.0.0.1:8000/rpc",
      }),
    });
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.ok).toBe(false);
    expect(body.error.code).toBe("unknown_operation");
    expect(runOperation).not.toHaveBeenCalled();
  });

  it("does not authorize generated operations outside the console boundary", async () => {
    const res = await app.request("/api/rpc", {
      method: "POST",
      headers: validConsoleHeaders,
      body: JSON.stringify({
        operation: "workflow.admin.auth.list",
        target: "http://127.0.0.1:8000/rpc",
      }),
    });

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error.code).toBe("unknown_operation");
  });

  it("does not authorize generic draft workspace mutations", async () => {
    const res = await app.request("/api/rpc", {
      method: "POST",
      headers: validConsoleHeaders,
      body: JSON.stringify({
        operation: "workflow.draft_workspaces.replace_document",
        target: "http://127.0.0.1:8000/rpc",
      }),
    });

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error.code).toBe("unknown_operation");
  });

  it("returns 400 for invalid JSON body", async () => {
    const res = await app.request("/api/rpc", {
      method: "POST",
      headers: validConsoleHeaders,
      body: "not json",
    });
    expect(res.status).toBe(400);
  });
});

describe("POST body size limit", () => {
  it("returns 413 when body exceeds 256 KiB", async () => {
    const bigBody = JSON.stringify({ data: "x".repeat(257 * 1024) });
    const res = await app.request("/api/rpc", {
      method: "POST",
      headers: validConsoleHeaders,
      body: bigBody,
    });
    expect(res.status).toBe(413);
  });
});

describe("error mapping", () => {
  it("maps upstream timeout to 504", async () => {
    const timeoutApp = makeApp({
      runOperation: failRunner("UpstreamTimeoutError", "timed out"),
    });
    const res = await timeoutApp.request("/api/rpc", {
      method: "POST",
      headers: validConsoleHeaders,
      body: JSON.stringify({
        operation: "workflow.health",
        target: "http://127.0.0.1:8000/rpc",
      }),
    });
    expect(res.status).toBe(504);
    const body = await res.json();
    expect(body.ok).toBe(false);
    expect(body.error.code).toBe("upstream_timeout");
    expect(body.exchange).toEqual({
      request: { method: "x" },
      response: { error: "timed out" },
    });
    expect(body.error.stack).toBeUndefined();
  });

  it("maps upstream connection error to 502", async () => {
    const connApp = makeApp({
      runOperation: failRunner("UpstreamConnectionError", "connection refused"),
    });
    const res = await connApp.request("/api/rpc", {
      method: "POST",
      headers: validConsoleHeaders,
      body: JSON.stringify({
        operation: "workflow.health",
        target: "http://127.0.0.1:8000/rpc",
      }),
    });
    expect(res.status).toBe(502);
    const body = await res.json();
    expect(body.ok).toBe(false);
    expect(body.error.code).toBe("upstream_unreachable");
    expect(body.error.stack).toBeUndefined();
  });

  it("maps RpcRemoteError to 502 with rpc_remote_error", async () => {
    const remoteApp = makeApp({
      runOperation: failRunner("RpcRemoteError", "method not found"),
    });
    const res = await remoteApp.request("/api/rpc", {
      method: "POST",
      headers: validConsoleHeaders,
      body: JSON.stringify({
        operation: "workflow.health",
        target: "http://127.0.0.1:8000/rpc",
      }),
    });
    expect(res.status).toBe(502);
    const body = await res.json();
    expect(body.ok).toBe(false);
    expect(body.error.code).toBe("rpc_remote_error");
    expect(body.error.stack).toBeUndefined();
  });

  it("maps InvalidTargetError to 400", async () => {
    const invalidApp = makeApp({
      runOperation: failRunner("InvalidTargetError", "bad target"),
    });
    const res = await invalidApp.request("/api/rpc", {
      method: "POST",
      headers: validConsoleHeaders,
      body: JSON.stringify({
        operation: "workflow.health",
        target: "not-a-url",
      }),
    });
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.ok).toBe(false);
    expect(body.error.code).toBe("invalid_target");
    expect(body.error.stack).toBeUndefined();
  });

  it("maps UnknownOperationError to 400", async () => {
    const unknownApp = makeApp({
      runOperation: failRunner("UnknownOperationError", "no such op"),
    });
    const res = await unknownApp.request("/api/rpc", {
      method: "POST",
      headers: validConsoleHeaders,
      body: JSON.stringify({
        operation: "workflow.health",
        target: "http://127.0.0.1:8000/rpc",
      }),
    });
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.ok).toBe(false);
    expect(body.error.code).toBe("unknown_operation");
  });

  it("never includes stack in error DTOs", async () => {
    const apps = [
      makeApp({ runOperation: failRunner("UpstreamTimeoutError", "t") }),
      makeApp({ runOperation: failRunner("UpstreamConnectionError", "c") }),
      makeApp({ runOperation: failRunner("RpcRemoteError", "r") }),
      makeApp({ runOperation: failRunner("InvalidTargetError", "i") }),
    ];
    for (const a of apps) {
      const res = await a.request("/api/rpc", {
        method: "POST",
        headers: validConsoleHeaders,
        body: JSON.stringify({
          operation: "workflow.health",
          target: "http://127.0.0.1:8000/rpc",
        }),
      });
      const body = await res.json();
      expect(body.error?.stack).toBeUndefined();
    }
  });
});

describe("static console routes", () => {
  it("serves the SPA and keeps unknown API paths as JSON 404", async () => {
    const consoleRoot = fs.mkdtempSync(path.join(os.tmpdir(), "wf-console-"));
    fs.mkdirSync(path.join(consoleRoot, "assets"));
    fs.writeFileSync(path.join(consoleRoot, "index.html"), "<main>console</main>");
    fs.writeFileSync(path.join(consoleRoot, "assets", "app.js"), "console.log('ok')");
    try {
      const staticApp = makeApp({ runOperation: okRunner, consoleRoot });

      const index = await staticApp.request("/workflows");
      expect(index.status).toBe(200);
      expect(await index.text()).toContain("console");

      const asset = await staticApp.request("/assets/app.js");
      expect(asset.status).toBe(200);
      expect(await asset.text()).toContain("ok");

      const unknownApi = await staticApp.request("/api/nope");
      expect(unknownApi.status).toBe(404);
      expect(await unknownApi.json()).toEqual({ error: "not found" });
    } finally {
      fs.rmSync(consoleRoot, { recursive: true, force: true });
    }
  });
});
