import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useRef } from "react";
import { MemoryRouter, Outlet, Route, Routes, useNavigate } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { connectToServer, callOperation } from "../connection/api.js";
import type { ConnectResponse } from "../connection/contracts.js";
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
      <output data-testid="executor-stable">
        {workspace.readExecutor === executorIdentity.current ? "yes" : "no"}
      </output>
      <button type="button" onClick={() => navigate("/console/drafts")}>Navigate to drafts</button>
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
    expect(screen.getByTestId("executor-stable")).toHaveTextContent("yes");
    expect(screen.getAllByText("Health check")).toHaveLength(1);
    expect(mockedCallOperation).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "Navigate to drafts" }));

    expect(await screen.findByText("Drafts route")).toBeInTheDocument();
    expect(screen.getAllByText("Health check")).toHaveLength(1);
    expect(screen.getByTestId("connected-target")).toHaveTextContent("http://one.example/rpc");
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
    expect(screen.getAllByText("Health check")).toHaveLength(1);
  });
});
