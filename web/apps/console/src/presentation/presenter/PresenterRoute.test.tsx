import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { PresentationSyncController } from "../sync/presentation-sync-state.js";
import { usePresentationSync } from "../sync/usePresentationSync.js";
import { PresenterRoute } from "./PresenterRoute.js";

vi.mock("../sync/usePresentationSync.js", () => ({
  usePresentationSync: vi.fn(),
}));

const mockedUsePresentationSync = vi.mocked(usePresentationSync);
const idleController = (): PresentationSyncController => ({
  state: { kind: "standalone" },
  startSession: vi.fn(async () => undefined),
  joinSession: vi.fn(async () => undefined),
  retry: vi.fn(),
  leaveSession: vi.fn(),
  endSession: vi.fn(),
});

beforeEach(() => {
  mockedUsePresentationSync.mockReturnValue(idleController());
});

afterEach(() => {
  cleanup();
  window.location.hash = "";
});

describe("PresenterRoute", () => {
  it("renders the first presenter note without audience runtime surfaces", () => {
    window.location.hash = "#scene/thesis/title";
    render(<PresenterRoute />);
    expect(screen.getByRole("main", { name: /lda.chat presenter notes/i })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Beat goal" })).toHaveTextContent(
      "Separate the AI-agent ambition from the implemented contribution.",
    );
    const anchorTerms = screen.getByRole("region", { name: "Anchor terms" });
    expect(anchorTerms).toHaveTextContent("AI-agent goal");
    expect(anchorTerms).toHaveTextContent("platform underneath");
    expect(screen.getByRole("region", { name: "Suggested wording" })).toHaveTextContent(
      "The title describes the original goal: an AI agent for workspace automation. My contribution is the platform underneath that agent.",
    );
    expect(screen.getByRole("navigation", { name: /presenter note navigation/i })).toHaveTextContent("1 / 39");
    expect(screen.getByRole("link", { name: "Next →" })).toHaveAttribute("href", "#scene/thesis/substrate");
    expect(screen.getByRole("link", { name: /open audience slide/i })).toHaveAttribute("href", "/present#scene/thesis/title");
    expect(screen.queryByText(/live target/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /run prepared workflow/i })).not.toBeInTheDocument();
  });

  it("keeps covered state local to the route", async () => {
    window.location.hash = "#scene/thesis/title";
    render(<PresenterRoute />);
    const checkbox = screen.getByRole("checkbox", { name: /mark covered/i });
    await userEvent.click(checkbox);
    expect(checkbox).toBeChecked();
  });

  it("navigates notes with arrow keys", () => {
    window.location.hash = "#scene/thesis/title";
    render(<PresenterRoute />);
    fireEvent.keyDown(window, { key: "ArrowRight" });
    expect(window.location.hash).toBe("#scene/thesis/substrate");
  });

  it("mounts presenter synchronization beside stable navigation and publishes canonical hashes", async () => {
    window.location.hash = "#scene/thesis/substrate";
    render(<PresenterRoute />);

    const navigation = screen.getByRole("navigation", { name: /presenter note navigation/i });
    expect(navigation).toContainElement(screen.getByRole("button", { name: /pair presentation/i }));
    expect(screen.getByRole("link", { name: /^Next →$/i })).toHaveAttribute(
      "href",
      "#scene/problem/direct-actions",
    );
    expect(screen.getAllByRole("link", { name: /Where is the AI agent/i })[0]).toHaveAttribute(
      "href",
      "#discuss/where-is-ai-agent",
    );
    expect(mockedUsePresentationSync).toHaveBeenLastCalledWith(expect.objectContaining({
      role: "presenter",
      currentHash: "#scene/thesis/substrate",
    }));

    await userEvent.click(screen.getByRole("link", { name: /previous/i }));
    expect(window.location.hash).toBe("#scene/thesis/title");
    fireEvent(window, new HashChangeEvent("hashchange"));
    expect(mockedUsePresentationSync).toHaveBeenLastCalledWith(expect.objectContaining({
      currentHash: "#scene/thesis/title",
    }));
  });

  it("applies audience hashes to notes and Q&A without publishing the old hash", () => {
    window.location.hash = "#scene/thesis/title";
    render(<PresenterRoute />);
    const applyRemoteHash = mockedUsePresentationSync.mock.calls.at(-1)?.[0].applyRemoteHash;
    expect(applyRemoteHash).toBeDefined();

    act(() => {
      applyRemoteHash?.("#scene/problem/direct-actions");
      fireEvent(window, new HashChangeEvent("hashchange"));
    });
    expect(screen.getByRole("region", { name: "Beat goal" })).toHaveTextContent(
      /Show why one successful chat is not yet automation/i,
    );
    expect(window.location.hash).toBe("#scene/problem/direct-actions");

    act(() => {
      applyRemoteHash?.("#discuss/where-is-ai-agent");
      fireEvent(window, new HashChangeEvent("hashchange"));
    });
    expect(screen.getByRole("heading", { name: /Where is the AI agent/i })).toBeInTheDocument();
    expect(mockedUsePresentationSync).toHaveBeenLastCalledWith(expect.objectContaining({
      currentHash: "#discuss/where-is-ai-agent",
    }));
  });

  it("ends presenter sessions after confirmation and displays ended state", async () => {
    let controllerState: PresentationSyncController["state"] = {
      kind: "connected",
      grant: {
        sessionId: "session-1",
        code: "ABC123",
        connectionToken: "token",
        websocketPath: "/api/presentation-sync/ws",
        snapshot: { hash: "#scene/thesis/title", revision: 1 },
      },
      snapshot: { hash: "#scene/thesis/title", revision: 1 },
      presence: { presenters: 1, audience: 1 },
    };
    const controller = {
      ...idleController(),
      get state() { return controllerState; },
    };
    mockedUsePresentationSync.mockReturnValue(controller);
    const { rerender } = render(<PresenterRoute />);

    await userEvent.click(screen.getByRole("button", { name: "End presentation" }));
    await userEvent.click(screen.getByRole("button", { name: "End presentation now" }));
    expect(controller.endSession).toHaveBeenCalledOnce();

    controllerState = { kind: "ended", reason: "presenter_ended" };
    rerender(<PresenterRoute />);
    expect(screen.getByText("The presenter ended this session.")).toBeInTheDocument();
  });

  it("keeps local navigation available after synchronization fails", () => {
    mockedUsePresentationSync.mockReturnValue({
      ...idleController(),
      state: { kind: "failed", message: "Socket unavailable", retryable: true },
    });
    window.location.hash = "#scene/thesis/title";
    render(<PresenterRoute />);

    fireEvent.keyDown(window, { key: "ArrowRight" });

    expect(window.location.hash).toBe("#scene/thesis/substrate");
    expect(screen.getByRole("alert")).toHaveTextContent("Socket unavailable");
  });

  it("advances from the latest hash during rapid consecutive navigation", () => {
    window.location.hash = "#scene/thesis/title";
    render(<PresenterRoute />);

    fireEvent.keyDown(window, { key: "ArrowRight" });
    fireEvent.keyDown(window, { key: "ArrowRight" });

    expect(window.location.hash).toBe("#scene/problem/direct-actions");
  });

  it("renders Q&A speaker guidance only in presenter mode", () => {
    window.location.hash = "#discuss/where-is-ai-agent";
    render(<PresenterRoute />);
    expect(screen.getByRole("heading", { name: /Where is the AI agent/i })).toBeInTheDocument();
    expect(screen.getByText(/Answer directly first/i)).toBeInTheDocument();
    expect(screen.getByText(/Abstract; Chapter 1 framing/i)).toBeInTheDocument();
    expect(screen.getByText(/Defense Q&A/i).closest("details")).toHaveAttribute("open");
    expect(screen.getByRole("link", { name: /Where is the AI agent in this thesis/i })).toHaveAttribute("aria-current", "page");
  });
});
