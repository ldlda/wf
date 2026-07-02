import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, within, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConnectionHeader } from "./ConnectionHeader.js";
import { initialState, connectionReducer } from "../app/state.js";

const getFirstSection = () => {
  const sections = document.querySelectorAll('section[aria-label="Connection"]');
  return sections[0] as HTMLElement;
};

const successData = {
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

beforeEach(() => {
  cleanup();
  try {
    sessionStorage.clear();
  } catch {
    // jsdom may not provide sessionStorage
  }
});

afterEach(() => {
  cleanup();
});

const renderWithDefaults = (overrides?: {
  onSubmit?: (target: string) => void;
  onDraftChange?: (value: string) => void;
  state?: ReturnType<typeof initialState>;
}) => {
  const state = overrides?.state ?? initialState();
  const onSubmit = overrides?.onSubmit ?? vi.fn();
  const onDraftChange = overrides?.onDraftChange ?? vi.fn();
  render(
    <ConnectionHeader state={state} onSubmit={onSubmit} onDraftChange={onDraftChange} />,
  );
  return { onSubmit, onDraftChange, state };
};

describe("ConnectionHeader", () => {
  it("renders default target and Connect button", () => {
    renderWithDefaults();
    expect(screen.getByLabelText("Workflow JSON-RPC URL")).toHaveValue(
      "http://127.0.0.1:8765/rpc",
    );
    expect(
      within(getFirstSection()).getByRole("button", { name: "Connect" }),
    ).toBeDefined();
  });

  it("does not automatically call the server", () => {
    const { onSubmit } = renderWithDefaults();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("shows connecting state and disables button during request", () => {
    const connectingState = connectionReducer(initialState(), {
      type: "submit",
      target: "http://127.0.0.1:8765/rpc",
    });
    renderWithDefaults({ state: connectingState });

    expect(
      within(getFirstSection()).getByRole("button", { name: "Connect" }),
    ).toBeDisabled();
    expect(
      within(getFirstSection()).getByTestId("phase-label"),
    ).toHaveTextContent("Connecting\u2026");
  });

  it("shows connected state with server details", () => {
    const connectedState = connectionReducer(initialState(), {
      type: "success",
      data: successData,
    });
    renderWithDefaults({ state: connectedState });

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

  it("retains typed value on failure", () => {
    const errorState = connectionReducer(initialState(), {
      type: "failure",
      code: "invalid_target",
      message: "bad target",
    });
    renderWithDefaults({
      state: { ...errorState, draftTarget: "http://bad:9999/rpc" },
    });
    expect(screen.getByLabelText("Workflow JSON-RPC URL")).toHaveValue(
      "http://bad:9999/rpc",
    );
    expect(
      within(getFirstSection()).getByTestId("error-message"),
    ).toHaveTextContent("bad target");
  });

  it("calls onSubmit with target when form submitted", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    renderWithDefaults({ onSubmit });

    await user.click(
      within(getFirstSection()).getByRole("button", { name: "Connect" }),
    );

    expect(onSubmit).toHaveBeenCalledWith(
      "http://127.0.0.1:8765/rpc",
    );
  });

  it("restored target still requires explicit connect", () => {
    try {
      sessionStorage.setItem(
        "lda.workflowConsole.target",
        "http://restored:9999/rpc",
      );
    } catch {
      // jsdom may not support sessionStorage
    }
    const { onSubmit } = renderWithDefaults();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
