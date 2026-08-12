import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useRef } from "react";
import { MemoryRouter, Outlet, Route, Routes, useNavigate } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { connectToServer, callOperation } from "../connection/api.js";
import type { ConnectResponse, RpcResponse } from "../connection/contracts.js";
import { useConsoleWorkspace } from "./context.js";
import { ConsoleWorkspace } from "./ConsoleWorkspace.js";

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
  exchange: { request: { target }, response: { status: 200 } },
  equivalentCli: "uv run wf status",
});

const successfulRead = (): RpcResponse => ({
  ok: true,
  operation: "workflow.capabilities.list",
  label: "List capabilities",
  interpreted: { items: [], nextCursor: null, total: 0 },
  exchange: { request: {}, response: { status: 200 } },
  equivalentCli: "uv run wf cap list",
  durationMs: 4,
});

const successfulWrite = (): RpcResponse => ({
  ok: true,
  operation: "workflow.draft_workspaces.validate",
  label: "Validate draft workspace",
  interpreted: {},
  exchange: { request: {}, response: { status: 200 } },
  equivalentCli: "uv run wf draft validate draft-report",
  durationMs: 4,
});

const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
};

const OutletProbe = () => {
  const workspace = useConsoleWorkspace();
  const executorIdentity = useRef<NonNullable<typeof workspace.readExecutor> | null>(null);
  if (workspace.readExecutor && executorIdentity.current === null) {
    executorIdentity.current = workspace.readExecutor;
  }
  const navigate = useNavigate();
  return (
    <>
      <output data-testid="connected-target">{workspace.connectedTarget ?? "none"}</output>
      <output data-testid="executor-state">{workspace.readExecutor ? "available" : "unavailable"}</output>
      <output data-testid="write-executor-state">
        {workspace.writeExecutor ? "available" : "unavailable"}
      </output>
      <output data-testid="executor-stable">
        {workspace.readExecutor === executorIdentity.current ? "yes" : "no"}
      </output>
      <output data-testid="evidence-ids">
        {workspace.connection.evidence.map((record) => record.id).join("|")}
      </output>
      <button type="button" onClick={() => navigate("/console/drafts")}>Navigate to drafts</button>
      <button
        type="button"
        disabled={workspace.readExecutor === null}
        onClick={() => {
          void workspace.readExecutor?.run("workflow.capabilities.list", {}, (value) => value);
        }}
      >
        Read capabilities
      </button>
      <button
        type="button"
        disabled={workspace.writeExecutor === null}
        onClick={() => {
          void workspace.writeExecutor?.run(
            "workflow.draft_workspaces.validate",
            { workspace_id: "draft-report" },
            (value) => value,
          );
        }}
      >
        Validate draft
      </button>
      <Outlet />
    </>
  );
};

const renderWorkspace = (initialEntry = "/console/discover") =>
  render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/console" element={<ConsoleWorkspace />}>
          <Route element={<OutletProbe />}>
            <Route path="discover" element={<p>Discover route</p>} />
            <Route path="drafts" element={<p>Drafts route</p>} />
          </Route>
        </Route>
      </Routes>
    </MemoryRouter>,
  );

beforeEach(() => {
  mockedConnectToServer.mockReset();
  mockedCallOperation.mockReset();
  sessionStorage.clear();
});

afterEach(() => cleanup());

describe("ConsoleWorkspace", () => {
  it("exposes no executor and issues no reads while disconnected", () => {
    renderWorkspace();

    expect(screen.getByTestId("executor-state")).toHaveTextContent("unavailable");
    expect(screen.getByTestId("write-executor-state")).toHaveTextContent("unavailable");
    expect(mockedConnectToServer).not.toHaveBeenCalled();
    expect(mockedCallOperation).not.toHaveBeenCalled();
  });

  it("records health once, exposes one target-scoped executor, and preserves evidence across routes", async () => {
    mockedConnectToServer.mockResolvedValue(successfulConnection("http://one.example/rpc"));
    renderWorkspace();

    await userEvent.click(screen.getByRole("button", { name: "Connect" }));

    expect(await screen.findByTestId("connected-target")).toHaveTextContent(
      "http://one.example/rpc",
    );
    expect(screen.getByTestId("executor-state")).toHaveTextContent("available");
    expect(screen.getByTestId("write-executor-state")).toHaveTextContent("available");
    expect(screen.getByTestId("executor-stable")).toHaveTextContent("yes");
    expect(screen.getByTestId("evidence-ids")).toHaveTextContent("workflow.health-0");
    expect(mockedCallOperation).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "Navigate to drafts" }));

    expect(await screen.findByText("Drafts route")).toBeInTheDocument();
    expect(screen.getByTestId("evidence-ids")).toHaveTextContent("workflow.health-0");
    expect(screen.getByTestId("connected-target")).toHaveTextContent("http://one.example/rpc");
  });

  it("keeps health and read evidence ids unique across reconnects", async () => {
    mockedConnectToServer.mockResolvedValue(successfulConnection("http://one.example/rpc"));
    mockedCallOperation.mockResolvedValue(successfulRead());
    renderWorkspace();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Connect" }));
    await user.click(await screen.findByRole("button", { name: "Read capabilities" }));
    await waitFor(() => {
      expect(screen.getByTestId("evidence-ids")).toHaveTextContent(
        "workflow.health-0|workflow.capabilities.list-1",
      );
    });

    await user.click(screen.getByRole("button", { name: "Reconnect" }));
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Read capabilities" })).toBeEnabled();
    });
    await user.click(screen.getByRole("button", { name: "Read capabilities" }));
    await waitFor(() => {
      const ids = screen.getByTestId("evidence-ids").textContent?.split("|") ?? [];
      expect(ids).toHaveLength(4);
      expect(new Set(ids).size).toBe(ids.length);
    });
  });

  it("drops a late read receipt from the old connection after reconnect", async () => {
    const oldRead = deferred<RpcResponse>();
    mockedConnectToServer
      .mockResolvedValueOnce(successfulConnection("http://one.example/rpc"))
      .mockResolvedValueOnce(successfulConnection("http://two.example/rpc"));
    mockedCallOperation.mockReturnValueOnce(oldRead.promise);
    renderWorkspace();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Connect" }));
    await user.click(await screen.findByRole("button", { name: "Read capabilities" }));
    expect(mockedCallOperation).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: "Reconnect" }));
    await waitFor(() => {
      expect(screen.getByTestId("connected-target")).toHaveTextContent(
        "http://two.example/rpc",
      );
      expect(screen.getByTestId("evidence-ids")).toHaveTextContent(
        "workflow.health-0|workflow.health-1",
      );
    });

    oldRead.resolve(successfulRead());
    await waitFor(() => {
      expect(screen.getByTestId("evidence-ids")).toHaveTextContent(
        "workflow.health-0|workflow.health-1",
      );
    });
  });

  it("drops a late write receipt from the old connection after reconnect", async () => {
    const oldWrite = deferred<RpcResponse>();
    mockedConnectToServer
      .mockResolvedValueOnce(successfulConnection("http://one.example/rpc"))
      .mockResolvedValueOnce(successfulConnection("http://two.example/rpc"));
    mockedCallOperation.mockReturnValueOnce(oldWrite.promise);
    renderWorkspace();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Connect" }));
    await user.click(await screen.findByRole("button", { name: "Validate draft" }));
    expect(mockedCallOperation).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: "Reconnect" }));
    await waitFor(() => {
      expect(screen.getByTestId("connected-target")).toHaveTextContent(
        "http://two.example/rpc",
      );
      expect(screen.getByTestId("evidence-ids")).toHaveTextContent(
        "workflow.health-0|workflow.health-1",
      );
    });

    oldWrite.resolve(successfulWrite());
    await act(async () => {
      await oldWrite.promise;
    });
    expect(screen.getByTestId("evidence-ids")).toHaveTextContent(
      "workflow.health-0|workflow.health-1",
    );
  });

  it("ignores a stale health response after a newer target connects", async () => {
    let resolveFirst!: (response: ConnectResponse) => void;
    const first = new Promise<ConnectResponse>((resolve) => {
      resolveFirst = resolve;
    });
    mockedConnectToServer.mockReturnValueOnce(first).mockResolvedValueOnce(
      successfulConnection("http://two.example/rpc"),
    );
    renderWorkspace();

    const user = userEvent.setup();
    const form = screen.getByLabelText("Workflow JSON-RPC URL").closest("form");
    expect(form).not.toBeNull();
    fireEvent.submit(form!);
    fireEvent.submit(form!);

    expect(await screen.findByTestId("connected-target")).toHaveTextContent(
      "http://two.example/rpc",
    );
    resolveFirst(successfulConnection("http://one.example/rpc"));

    await waitFor(() => {
      expect(screen.getByTestId("connected-target")).toHaveTextContent(
        "http://two.example/rpc",
      );
    });
    expect(screen.getByTestId("evidence-ids")).toHaveTextContent("workflow.health-0");
  });
});
