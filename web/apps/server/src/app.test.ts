import { describe, it, expect, vi } from "vitest";
import { createApp, type RunOperation } from "./app.js";
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

const app = createApp({ runOperation: okRunner });

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
      headers: { "content-type": "application/json" },
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
      headers: { "content-type": "application/json" },
      body: JSON.stringify({}),
    });
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.ok).toBe(false);
    expect(body.error.code).toBe("invalid_target");
  });

  it("returns a decode error when health interpretation is malformed", async () => {
    const malformedApp = createApp({
      runOperation: async () => makeExchange({ interpreted: { status: "ok" } }),
    });
    const res = await malformedApp.request("/api/connect", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ target: "http://127.0.0.1:8000/rpc" }),
    });
    expect(res.status).toBe(502);
    const body = await res.json();
    expect(body.ok).toBe(false);
    expect(body.error.code).toBe("rpc_decode_error");
  });
});

describe("POST /api/rpc", () => {
  it("invokes the requested operation", async () => {
    const res = await app.request("/api/rpc", {
      method: "POST",
      headers: { "content-type": "application/json" },
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

  it("returns 400 for unknown operation", async () => {
    const res = await app.request("/api/rpc", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        operation: "foo.bar",
        target: "http://127.0.0.1:8000/rpc",
      }),
    });
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.ok).toBe(false);
    expect(body.error.code).toBe("unknown_operation");
  });

  it("returns 400 for invalid JSON body", async () => {
    const res = await app.request("/api/rpc", {
      method: "POST",
      headers: { "content-type": "application/json" },
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
      headers: { "content-type": "application/json" },
      body: bigBody,
    });
    expect(res.status).toBe(413);
  });
});

describe("error mapping", () => {
  it("maps upstream timeout to 504", async () => {
    const timeoutApp = createApp({
      runOperation: failRunner("UpstreamTimeoutError", "timed out"),
    });
    const res = await timeoutApp.request("/api/rpc", {
      method: "POST",
      headers: { "content-type": "application/json" },
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
    const connApp = createApp({
      runOperation: failRunner("UpstreamConnectionError", "connection refused"),
    });
    const res = await connApp.request("/api/rpc", {
      method: "POST",
      headers: { "content-type": "application/json" },
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
    const remoteApp = createApp({
      runOperation: failRunner("RpcRemoteError", "method not found"),
    });
    const res = await remoteApp.request("/api/rpc", {
      method: "POST",
      headers: { "content-type": "application/json" },
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
    const invalidApp = createApp({
      runOperation: failRunner("InvalidTargetError", "bad target"),
    });
    const res = await invalidApp.request("/api/rpc", {
      method: "POST",
      headers: { "content-type": "application/json" },
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
    const unknownApp = createApp({
      runOperation: failRunner("UnknownOperationError", "no such op"),
    });
    const res = await unknownApp.request("/api/rpc", {
      method: "POST",
      headers: { "content-type": "application/json" },
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
      createApp({ runOperation: failRunner("UpstreamTimeoutError", "t") }),
      createApp({ runOperation: failRunner("UpstreamConnectionError", "c") }),
      createApp({ runOperation: failRunner("RpcRemoteError", "r") }),
      createApp({ runOperation: failRunner("InvalidTargetError", "i") }),
    ];
    for (const a of apps) {
      const res = await a.request("/api/rpc", {
        method: "POST",
        headers: { "content-type": "application/json" },
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
      const staticApp = createApp({ runOperation: okRunner, consoleRoot });

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
