import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, within, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConnectionHeader } from "./ConnectionHeader.js";

vi.mock("../connection/api.js", () => ({
  connectToServer: vi.fn(),
}));

import { connectToServer } from "../connection/api.js";
const mockConnect = vi.mocked(connectToServer);

beforeEach(() => {
  cleanup();
  mockConnect.mockReset();
  try {
    sessionStorage.clear();
  } catch {
    // jsdom may not provide sessionStorage
  }
});

const successResponse = {
  ok: true,
  connection: {
    status: "connected",
    target: "http://127.0.0.1:8765/rpc",
    serverStatus: "ok",
    storeRoot: "/tmp/store",
    durationMs: 12,
  },
  exchange: { request: {}, response: {} },
  equivalentCli: "uv run wf status",
} as const;

const getFirstSection = () => {
  const sections = document.querySelectorAll('section[aria-label="Connection"]');
  return sections[0] as HTMLElement;
};

describe("ConnectionHeader", () => {
  it("renders default target and Connect button", () => {
    render(<ConnectionHeader />);
    expect(screen.getByLabelText("Workflow JSON-RPC URL")).toHaveValue(
      "http://127.0.0.1:8765/rpc",
    );
    expect(
      within(getFirstSection()).getByRole("button", { name: "Connect" }),
    ).toBeDefined();
  });

  it("does not automatically call the server", () => {
    render(<ConnectionHeader />);
    expect(mockConnect).not.toHaveBeenCalled();
  });

  it("shows connecting state and disables button during request", async () => {
    const user = userEvent.setup();
    let resolveConnect!: (value: typeof successResponse) => void;
    mockConnect.mockReturnValue(
      new Promise((r) => {
        resolveConnect = r;
      }),
    );

    render(<ConnectionHeader />);
    await user.click(
      within(getFirstSection()).getByRole("button", { name: "Connect" }),
    );

    expect(
      within(getFirstSection()).getByRole("button", { name: "Connect" }),
    ).toBeDisabled();
    expect(
      within(getFirstSection()).getByTestId("phase-label"),
    ).toHaveTextContent("Connecting\u2026");

    resolveConnect(successResponse);
  });

  it("shows connected state with server details", async () => {
    const user = userEvent.setup();
    mockConnect.mockResolvedValue(successResponse);

    render(<ConnectionHeader />);
    await user.click(
      within(getFirstSection()).getByRole("button", { name: "Connect" }),
    );

    expect(
      within(getFirstSection()).getByTestId("phase-label"),
    ).toHaveTextContent("Connected");
    expect(
      within(getFirstSection()).getByTestId("server-status"),
    ).toHaveTextContent("ok");
    expect(
      within(getFirstSection()).getByTestId("store-root"),
    ).toHaveTextContent("/tmp/store");
    expect(
      within(getFirstSection()).getByTestId("duration-ms"),
    ).toHaveTextContent("12ms");
    expect(
      within(getFirstSection()).getByRole("button", { name: "Reconnect" }),
    ).toBeDefined();
  });

  it("retains typed value on failure", async () => {
    const user = userEvent.setup();
    mockConnect.mockResolvedValue({
      ok: false,
      error: { code: "invalid_target", message: "bad target" },
      exchange: { request: null, response: null },
    });

    render(<ConnectionHeader />);
    const input = screen.getByLabelText("Workflow JSON-RPC URL");
    await user.clear(input);
    await user.type(input, "http://bad:9999/rpc");
    await user.click(
      within(getFirstSection()).getByRole("button", { name: "Connect" }),
    );

    expect(input).toHaveValue("http://bad:9999/rpc");
    expect(
      within(getFirstSection()).getByTestId("error-message"),
    ).toHaveTextContent("bad target");
  });

  it("restored target still requires explicit connect", async () => {
    try {
      sessionStorage.setItem(
        "lda.workflowConsole.target",
        "http://restored:9999/rpc",
      );
    } catch {
      // jsdom may not support sessionStorage
    }

    render(<ConnectionHeader />);
    expect(mockConnect).not.toHaveBeenCalled();
  });
});
