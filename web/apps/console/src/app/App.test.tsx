import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App.js";
import { callOperation, connectToServer } from "../connection/api.js";
import type { ConnectResponse, RpcResponse } from "../connection/contracts.js";

vi.mock("../connection/api.js", () => ({
  connectToServer: vi.fn(),
  callOperation: vi.fn(),
}));

const mockedConnectToServer = vi.mocked(connectToServer);
const mockedCallOperation = vi.mocked(callOperation);

const successfulConnection = (target: string): ConnectResponse => ({
  ok: true,
  connection: {
    status: "connected",
    target,
    serverStatus: "ok",
    storeRoot: "/tmp/store",
    durationMs: 11,
  },
  exchange: { request: {}, response: {} },
  equivalentCli: "uv run wf status",
});

const successfulSources = (id: string): RpcResponse => ({
  ok: true,
  operation: "workflow.sources.list",
  label: "List sources",
  interpreted: {
    sources: [
      {
        id,
        kind: "python",
        enabled: true,
        description: null,
        counts: {
          tools: 1,
          nodeSpecs: 1,
          reducers: 0,
          prompts: 0,
          resources: 0,
        },
      },
    ],
    total: 1,
    nextCursor: null,
  },
  exchange: { request: {}, response: {} },
  equivalentCli: "uv run wf source list",
  durationMs: 7,
});

const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
};

beforeEach(() => {
  mockedConnectToServer.mockReset();
  mockedCallOperation.mockReset();
  sessionStorage.clear();
});

afterEach(() => {
  cleanup();
});

describe("App", () => {
  it("shows source inventory errors from rejected source refreshes", async () => {
    mockedConnectToServer.mockResolvedValue(
      successfulConnection("http://127.0.0.1:8765/rpc"),
    );
    mockedCallOperation.mockRejectedValue(new Error("source refresh failed"));

    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: "Connect" }));

    expect(await screen.findByTestId("sources-error")).toHaveTextContent(
      "source refresh failed",
    );
  });

  it("ignores stale source inventory responses after reconnect", async () => {
    const firstSources = deferred<RpcResponse>();
    const secondSources = deferred<RpcResponse>();
    mockedConnectToServer
      .mockResolvedValueOnce(successfulConnection("http://first.example/rpc"))
      .mockResolvedValueOnce(successfulConnection("http://second.example/rpc"));
    mockedCallOperation
      .mockReturnValueOnce(firstSources.promise)
      .mockReturnValueOnce(secondSources.promise);

    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: "Connect" }));
    await screen.findByTestId("sources-loading");

    await userEvent.click(screen.getByRole("button", { name: "Reconnect" }));
    secondSources.resolve(successfulSources("local.second"));
    firstSources.resolve(successfulSources("local.first"));

    expect(await screen.findByTestId("source-id-local.second")).toHaveTextContent(
      "local.second",
    );
    await waitFor(() => {
      expect(screen.queryByTestId("source-id-local.first")).toBeNull();
    });
  });
});
