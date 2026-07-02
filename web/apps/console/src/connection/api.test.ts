import { describe, it, expect, vi, beforeEach } from "vitest";
import { connectToServer, callOperation } from "./api.js";

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

beforeEach(() => {
  mockFetch.mockReset();
});

const jsonResponse = (data: unknown, status = 200) =>
  Promise.resolve(
    new Response(JSON.stringify(data), {
      status,
      headers: { "content-type": "application/json" },
    }),
  );

describe("connectToServer", () => {
  it("posts the exact target to /api/connect", async () => {
    mockFetch.mockReturnValue(
      jsonResponse({
        ok: true,
        connection: {
          status: "connected",
          target: "http://127.0.0.1:8000/rpc",
          serverStatus: "ok",
          storeRoot: "/tmp/store",
          durationMs: 10,
        },
        exchange: { request: {}, response: {} },
        equivalentCli: "uv run wf status",
      }),
    );

    const result = await connectToServer("http://127.0.0.1:8000/rpc");

    expect(mockFetch).toHaveBeenCalledWith("/api/connect", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ target: "http://127.0.0.1:8000/rpc" }),
    });
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.connection.status).toBe("connected");
    }
  });

  it("returns typed failure DTO instead of throwing for HTTP errors", async () => {
    mockFetch.mockReturnValue(
      jsonResponse(
        {
          ok: false,
          error: { code: "invalid_target", message: "missing target" },
          exchange: { request: null, response: null },
        },
        400,
      ),
    );

    const result = await connectToServer("bad-url");
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.code).toBe("invalid_target");
    }
  });

  it("accepts future server error codes without rejecting the response", async () => {
    mockFetch.mockReturnValue(
      jsonResponse(
        {
          ok: false,
          error: { code: "new_server_code", message: "future failure" },
          exchange: { request: null, response: null },
        },
        502,
      ),
    );

    const result = await connectToServer("http://127.0.0.1:8000/rpc");
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.code).toBe("new_server_code");
    }
  });
});

describe("callOperation", () => {
  it("posts operation, target, and params to /api/rpc", async () => {
    mockFetch.mockReturnValue(
      jsonResponse({
        ok: true,
        operation: "workflow.sources.list",
        label: "List sources",
        interpreted: { sources: [], total: 0 },
        exchange: { request: {}, response: {} },
        equivalentCli: "uv run wf source list",
        durationMs: 5,
      }),
    );

    const result = await callOperation(
      "workflow.sources.list",
      "http://127.0.0.1:8000/rpc",
      { limit: 10 },
    );

    expect(mockFetch).toHaveBeenCalledWith("/api/rpc", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        operation: "workflow.sources.list",
        target: "http://127.0.0.1:8000/rpc",
        params: { limit: 10 },
      }),
    });
    expect(result.ok).toBe(true);
  });

  it("defaults params to empty object", async () => {
    mockFetch.mockReturnValue(
      jsonResponse({
        ok: true,
        operation: "workflow.health",
        label: "Health check",
        interpreted: { status: "ok" },
        exchange: { request: {}, response: {} },
        equivalentCli: "uv run wf status",
        durationMs: 3,
      }),
    );

    await callOperation("workflow.health", "http://127.0.0.1:8000/rpc");
    const body = JSON.parse(
      (mockFetch.mock.calls[0] as [string, { body: string }])[1].body,
    );
    expect(body.params).toEqual({});
  });
});

describe("error handling", () => {
  it("throws for malformed JSON response", async () => {
    mockFetch.mockReturnValue(
      Promise.resolve(new Response("not json", { status: 200 })),
    );

    await expect(
      connectToServer("http://127.0.0.1:8000/rpc"),
    ).rejects.toThrow("malformed JSON");
  });

  it("throws for empty response", async () => {
    mockFetch.mockReturnValue(Promise.resolve(new Response("", { status: 200 })));

    await expect(
      connectToServer("http://127.0.0.1:8000/rpc"),
    ).rejects.toThrow("console backend returned an empty response (HTTP 200)");
  });

  it("throws for structurally malformed JSON response", async () => {
    mockFetch.mockReturnValue(jsonResponse({ ok: true, connection: {} }));

    await expect(
      connectToServer("http://127.0.0.1:8000/rpc"),
    ).rejects.toThrow("malformed response from server:");
  });

  it("throws on network failure", async () => {
    mockFetch.mockReturnValue(Promise.reject(new Error("network error")));

    await expect(
      connectToServer("http://127.0.0.1:8000/rpc"),
    ).rejects.toThrow("network error");
  });
});
