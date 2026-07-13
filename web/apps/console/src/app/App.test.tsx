import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App.js";
import { AppRoutes } from "./AppRoutes.js";
import { callOperation, connectToServer } from "../connection/api.js";
import type { RpcResponse } from "../connection/contracts.js";

vi.mock("../connection/api.js", () => ({
  connectToServer: vi.fn(),
  callOperation: vi.fn(),
}));

const mockedConnectToServer = vi.mocked(connectToServer);
const mockedCallOperation = vi.mocked(callOperation);

const successfulConnection = (target: string) => ({
  ok: true as const,
  connection: {
    status: "connected" as const,
    target,
    serverStatus: "ok" as const,
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

const lifecycleOk = {
  ok: true as const,
  operation: "workflow.artifacts.list" as const,
  label: "List artifacts",
  interpreted: { items: [], total: 0, nextCursor: null },
  exchange: { request: {}, response: {} },
  equivalentCli: "uv run wf artifact list",
  durationMs: 5,
};

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
    let latestSourcesDeferred = firstSources;
    mockedConnectToServer
      .mockResolvedValueOnce(successfulConnection("http://first.example/rpc"))
      .mockResolvedValueOnce(successfulConnection("http://second.example/rpc"));
    mockedCallOperation.mockImplementation((op: string) => {
      if (op === "workflow.sources.list") return latestSourcesDeferred.promise;
      return Promise.resolve(lifecycleOk);
    });

    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: "Connect" }));

    latestSourcesDeferred = secondSources;
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

  it("mounts lifecycle explorer after connect", async () => {
    mockedConnectToServer.mockResolvedValue(
      successfulConnection("http://127.0.0.1:8765/rpc"),
    );
    mockedCallOperation.mockImplementation((op: string) => {
      if (op === "workflow.sources.list") {
        return Promise.resolve({
          ok: true as const,
          operation: "workflow.sources.list" as const,
          label: "List sources",
          interpreted: { sources: [], total: 0, nextCursor: null },
          exchange: { request: {}, response: {} },
          equivalentCli: "uv run wf source list",
          durationMs: 5,
        });
      }
      if (op === "workflow.deployments.inspect") {
        return Promise.resolve({
          ok: false as const,
          error: { code: "rpc_remote_error", message: "not found" },
          exchange: { request: {}, response: {} },
        });
      }
      return Promise.resolve(lifecycleOk);
    });

    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: "Connect" }));

    await waitFor(() => {
      expect(screen.getByTestId("lifecycle-explorer")).toBeInTheDocument();
    });
    expect(screen.getByLabelText("lda report workflow demo")).toBeInTheDocument();
  });

  it("always renders demo panel even without connection", async () => {
    mockedConnectToServer.mockRejectedValue(new Error("connection refused"));

    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: "Connect" }));

    await waitFor(() => {
      expect(screen.getByLabelText("lda report workflow demo")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /start presentation/i })).toBeDisabled();
  });

  it("shows replay mode button even without connection", async () => {
    render(<App />);

    expect(screen.getByRole("button", { name: "Replay" })).toBeVisible();
    expect(screen.getByRole("button", { name: /start presentation/i })).toBeDisabled();

    await userEvent.click(screen.getByRole("button", { name: "Replay" }));
    expect(screen.getByRole("button", { name: /start presentation/i })).toBeEnabled();
  });

  it("routes to presentation mode separately from the console", () => {
    render(
      <MemoryRouter initialEntries={["/present"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect(screen.getByRole("main", { name: /lda.chat presentation/i })).toBeInTheDocument();
    expect(screen.queryByLabelText("Lifecycle Explorer")).toBeNull();
  });

  it("routes to read-only presenter notes separately from presentation mode", async () => {
    window.location.hash = "#scene/thesis/title";
    render(
      <MemoryRouter initialEntries={["/presenter"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("main", { name: /lda.chat presenter notes/i })).toBeInTheDocument();
    expect(screen.queryByRole("main", { name: /lda.chat presentation/i })).not.toBeInTheDocument();
  });
});
