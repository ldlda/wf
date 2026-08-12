import { Hono } from "hono";
import { bodyLimit } from "hono/body-limit";
import type { ContentfulStatusCode } from "hono/utils/http-status";
import {
  type OperationExchange,
  type OperationName,
  type WorkflowHealthInterpreted,
} from "@lda/workflow-rpc";
import type { upgradeWebSocket } from "@hono/node-server";
import { addPresentationSyncRoutes } from "./presentation-sync/routes.js";
import type { PresentationRoomService } from "./presentation-sync/rooms.js";
import type { BrowserOperationPolicy } from "./browser-operation-policy.js";
import { addStaticRoutes, validateConsoleRoot } from "./static.js";

export type RunOperation = (
  operation: OperationName,
  target: string,
  params: unknown,
) => Promise<OperationExchange>;

type BrowserErrorCode =
  | "invalid_target"
  | "request_rejected"
  | "unknown_operation"
  | "operation_disabled"
  | "upstream_unreachable"
  | "upstream_timeout"
  | "rpc_remote_error"
  | "rpc_protocol_error"
  | "rpc_decode_error"
  | "response_too_large";

const CONSOLE_REQUEST_HEADER = "x-workflow-console";

type ConsoleRequestRejection = {
  readonly status: 403 | 415;
  readonly message: string;
};

/**
 * Blocks browser-simple and cross-origin POSTs before they can reach an RPC.
 * The Vite proxy preserves the console-facing origin in the request URL, so
 * comparing against it keeps development and production on the same contract.
 */
const consoleRequestRejection = (
  request: Request,
  trustedOrigins: ReadonlySet<string>,
): ConsoleRequestRejection | null => {
  const contentType = request.headers
    .get("content-type")
    ?.split(";", 1)[0]
    ?.trim()
    .toLowerCase();
  if (contentType !== "application/json") {
    return {
      status: 415,
      message: "console POST requests require application/json",
    };
  }
  if (request.headers.get(CONSOLE_REQUEST_HEADER) !== "1") {
    return {
      status: 403,
      message: "console POST request header is missing or invalid",
    };
  }

  const fetchSite = request.headers.get("sec-fetch-site")?.toLowerCase();
  if (
    fetchSite !== undefined &&
    fetchSite !== "same-origin" &&
    fetchSite !== "none"
  ) {
    return { status: 403, message: "cross-origin console POST rejected" };
  }

  const origin = request.headers.get("origin");
  if (origin !== null) {
    let parsedOrigin: URL;
    try {
      parsedOrigin = new URL(origin);
    } catch {
      return { status: 403, message: "invalid console request origin" };
    }
    if (
      parsedOrigin.origin !== new URL(request.url).origin &&
      !trustedOrigins.has(parsedOrigin.origin)
    ) {
      return { status: 403, message: "cross-origin console POST rejected" };
    }
  }
  return null;
};

const rejectInvalidConsoleRequest = (
  request: Request,
  trustedOrigins: ReadonlySet<string>,
):
  | {
      readonly status: 403 | 415;
      readonly body: {
        readonly ok: false;
        readonly error: {
          readonly code: "request_rejected";
          readonly message: string;
        };
        readonly exchange: {
          readonly request: null;
          readonly response: null;
        };
      };
    }
  | null => {
  const rejection = consoleRequestRejection(request, trustedOrigins);
  if (rejection === null) return null;
  return {
    status: rejection.status,
    body: {
      ok: false,
      error: { code: "request_rejected", message: rejection.message },
      exchange: { request: null, response: null },
    },
  };
};

const isHealthInterpreted = (
  value: unknown,
): value is WorkflowHealthInterpreted =>
  typeof value === "object" &&
  value !== null &&
  "status" in value &&
  value.status === "ok" &&
  "storeRoot" in value &&
  typeof value.storeRoot === "string";

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
  readonly presentationSync: {
    readonly rooms: PresentationRoomService;
    readonly upgradeWebSocket: typeof upgradeWebSocket;
  };
  readonly browserOperationPolicy: BrowserOperationPolicy;
  readonly trustedOrigins?: ReadonlySet<string>;
  readonly consoleRoot?: string;
}): Hono {
  const {
    runOperation,
    presentationSync,
    browserOperationPolicy,
    trustedOrigins = new Set(),
    consoleRoot,
  } = dependencies;
  const app = new Hono();

  addPresentationSyncRoutes(app, presentationSync);

  app.get("/api/health", (c) =>
    c.json({ ok: true, status: "ok" }),
  );

  app.use("/api/connect", bodyLimit({ maxSize: 256 * 1024 }));
  app.post("/api/connect", async (c) => {
    const rejected = rejectInvalidConsoleRequest(c.req.raw, trustedOrigins);
    if (rejected !== null) return c.json(rejected.body, rejected.status);

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
      if (!isHealthInterpreted(exchange.interpreted)) {
        return c.json(
          {
            ok: false,
            error: {
              code: "rpc_decode_error",
              message: "workflow.health returned an unexpected shape",
            },
            exchange: exchange.exchange,
          },
          502,
        );
      }
      return c.json({
        ok: true,
        connection: {
          status: "connected",
          target: exchange.target,
          serverStatus: "ok",
          storeRoot: exchange.interpreted.storeRoot,
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
    const rejected = rejectInvalidConsoleRequest(c.req.raw, trustedOrigins);
    if (rejected !== null) return c.json(rejected.body, rejected.status);

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

    if (!body.operation || typeof body.operation !== "string") {
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

    const decision = browserOperationPolicy.classify(body.operation);
    if (decision === "unknown") {
      return c.json(
        {
          ok: false,
          error: {
            code: "unknown_operation",
            message: `unknown operation: ${body.operation}`,
          },
          exchange: { request: null, response: null },
        },
        400,
      );
    }
    if (decision === "disabled") {
      return c.json(
        {
          ok: false,
          error: {
            code: "operation_disabled",
            message:
              "workflow.capabilities.call is disabled for this console server",
          },
          exchange: { request: null, response: null },
        },
        403,
      );
    }

    // The policy only returns allowed for the authored or conditional RPC names.
    const operation = body.operation as OperationName;

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
        operation,
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
