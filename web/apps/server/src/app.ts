import { Hono } from "hono";
import { bodyLimit } from "hono/body-limit";
import type { ContentfulStatusCode } from "hono/utils/http-status";
import type { OperationExchange, OperationName } from "@lda/workflow-rpc";
import { addStaticRoutes, validateConsoleRoot } from "./static.js";

export type RunOperation = (
  operation: OperationName,
  target: string,
  params: unknown,
) => Promise<OperationExchange>;

type BrowserErrorCode =
  | "invalid_target"
  | "unknown_operation"
  | "upstream_unreachable"
  | "upstream_timeout"
  | "rpc_remote_error"
  | "rpc_protocol_error"
  | "rpc_decode_error"
  | "response_too_large";

const VALID_OPERATIONS: ReadonlySet<string> = new Set([
  "workflow.health",
  "workflow.sources.list",
]);

const mapErrorToStatus = (
  tag: string,
): { status: ContentfulStatusCode; code: BrowserErrorCode } => {
  switch (tag) {
    case "InvalidTargetError":
      return { status: 400, code: "invalid_target" };
    case "UnknownOperationError":
      return { status: 400, code: "unknown_operation" };
    case "UpstreamConnectionError":
      return { status: 502, code: "upstream_unreachable" };
    case "UpstreamTimeoutError":
      return { status: 504, code: "upstream_timeout" };
    case "RpcRemoteError":
      return { status: 502, code: "rpc_remote_error" };
    case "RpcProtocolError":
      return { status: 502, code: "rpc_protocol_error" };
    case "RpcDecodeError":
      return { status: 502, code: "rpc_decode_error" };
    case "UpstreamResponseTooLargeError":
      return { status: 502, code: "response_too_large" };
    default:
      return { status: 500, code: "rpc_protocol_error" };
  }
};

export function createApp(dependencies: {
  readonly runOperation: RunOperation;
  readonly consoleRoot?: string;
}): Hono {
  const { runOperation, consoleRoot } = dependencies;
  const app = new Hono();

  app.get("/api/health", (c) =>
    c.json({ ok: true, status: "ok" }),
  );

  app.use("/api/connect", bodyLimit({ maxSize: 256 * 1024 }));
  app.post("/api/connect", async (c) => {
    let body: { target?: string };
    try {
      body = await c.req.json();
    } catch {
      return c.json(
        {
          ok: false,
          error: { code: "rpc_protocol_error", message: "invalid JSON body" },
          exchange: { request: null, response: null },
        },
        400,
      );
    }
    if (!body.target || typeof body.target !== "string") {
      return c.json(
        {
          ok: false,
          error: { code: "invalid_target", message: "missing target" },
          exchange: { request: null, response: null },
        },
        400,
      );
    }
    try {
      const exchange = await runOperation(
        "workflow.health",
        body.target,
        {},
      );
      return c.json({
        ok: true,
        connection: {
          status: "connected",
          target: exchange.target,
          serverStatus: "ok",
          storeRoot: (
            exchange.interpreted as { storeRoot?: string; store_root?: string }
          ).storeRoot ?? (
            exchange.interpreted as { storeRoot?: string; store_root?: string }
          ).store_root ?? "",
          durationMs: exchange.durationMs,
        },
        exchange: exchange.exchange,
        equivalentCli: exchange.equivalentCli,
      });
    } catch (e: unknown) {
      const tag =
        e && typeof e === "object" && "_tag" in e
          ? String((e as { _tag: unknown })._tag)
          : "Error";
      const { status, code } = mapErrorToStatus(tag);
      const msg = e instanceof Error ? e.message : String(e);
      return c.json(
        {
          ok: false,
          error: { code, message: msg },
          exchange: exchangeFromError(e),
        },
        status,
      );
    }
  });

  app.use("/api/rpc", bodyLimit({ maxSize: 256 * 1024 }));
  app.post("/api/rpc", async (c) => {
    let body: { operation?: string; target?: string; params?: unknown };
    try {
      body = await c.req.json();
    } catch {
      return c.json(
        {
          ok: false,
          error: { code: "rpc_protocol_error", message: "invalid JSON body" },
          exchange: { request: null, response: null },
        },
        400,
      );
    }

    if (
      !body.operation ||
      typeof body.operation !== "string" ||
      !VALID_OPERATIONS.has(body.operation)
    ) {
      return c.json(
        {
          ok: false,
          error: {
            code: "unknown_operation",
            message: `unknown operation: ${body.operation ?? "undefined"}`,
          },
          exchange: { request: null, response: null },
        },
        400,
      );
    }

    if (!body.target || typeof body.target !== "string") {
      return c.json(
        {
          ok: false,
          error: { code: "invalid_target", message: "missing target" },
          exchange: { request: null, response: null },
        },
        400,
      );
    }

    try {
      const exchange = await runOperation(
        body.operation as OperationName,
        body.target,
        body.params ?? {},
      );
      return c.json({
        ok: true,
        operation: exchange.operation,
        label: exchange.label,
        interpreted: exchange.interpreted,
        exchange: exchange.exchange,
        equivalentCli: exchange.equivalentCli,
        durationMs: exchange.durationMs,
      });
    } catch (e: unknown) {
      const tag =
        e && typeof e === "object" && "_tag" in e
          ? String((e as { _tag: unknown })._tag)
          : "Error";
      const { status, code } = mapErrorToStatus(tag);
      const msg = e instanceof Error ? e.message : String(e);
      return c.json(
        {
          ok: false,
          error: { code, message: msg },
          exchange: exchangeFromError(e),
        },
        status,
      );
    }
  });

  if (consoleRoot) {
    validateConsoleRoot(consoleRoot);
    addStaticRoutes(app, { consoleRoot });
  }

  return app;
}

const exchangeFromError = (
  error: unknown,
): { readonly request: unknown | null; readonly response: unknown | null } => {
  if (error && typeof error === "object" && "exchange" in error) {
    const exchange = (error as { readonly exchange?: unknown }).exchange;
    if (exchange && typeof exchange === "object") {
      return {
        request:
          "request" in exchange
            ? (exchange as { readonly request?: unknown }).request ?? null
            : null,
        response:
          "response" in exchange
            ? (exchange as { readonly response?: unknown }).response ?? null
            : null,
      };
    }
  }
  return { request: null, response: null };
};
