import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { PresentationRole, SessionGrant } from "@lda/presentation-sync";
import type {
  PresentationSyncController,
  PresentationSyncState,
} from "./presentation-sync-state.js";
import { PresentationPairingPanel } from "./PresentationPairingPanel.js";

afterEach(() => cleanup());

const grant: SessionGrant = {
  sessionId: "session-1",
  code: "ABC123",
  connectionToken: "token-1",
  websocketPath: "/api/presentation-sync/ws",
  snapshot: { hash: "#scene/thesis/title", revision: 0 },
};

const connectedState = (
  kind: "waiting" | "connected" | "reconnecting" = "connected",
): PresentationSyncState => ({
  kind,
  grant,
  snapshot: grant.snapshot,
  presence: { presenters: 1, audience: 2 },
});

const controllerFor = (
  state: PresentationSyncState,
): PresentationSyncController => ({
  state,
  startSession: vi.fn(async () => {}),
  joinSession: vi.fn(async () => {}),
  retry: vi.fn(),
  leaveSession: vi.fn(),
  endSession: vi.fn(),
});

const renderPanel = (
  role: PresentationRole,
  state: PresentationSyncState,
) => {
  const controller = controllerFor(state);
  const view = render(
    <PresentationPairingPanel role={role} controller={controller} />,
  );
  return { controller, ...view };
};

describe("PresentationPairingPanel", () => {
  beforeEach(() => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: vi.fn(async () => {}) },
    });
  });

  it("keeps the standalone surface collapsed until Pair presentation is opened", async () => {
    const user = userEvent.setup();
    renderPanel("audience", { kind: "standalone" });

    const trigger = screen.getByRole("button", { name: "Pair presentation" });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("button", { name: "Start session" })).toBeNull();

    await user.click(trigger);

    expect(screen.getByRole("button", { name: "Start session" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Pairing code" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Join session" })).toBeInTheDocument();
  });

  it("disables creation and joining controls while an operation is in flight", () => {
    const { rerender } = renderPanel("presenter", { kind: "creating" });
    expect(screen.getByRole("button", { name: "Start session" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Join session" })).toBeDisabled();

    rerender(
      <PresentationPairingPanel
        role="presenter"
        controller={controllerFor({ kind: "joining", code: "ABC123" })}
      />,
    );
    expect(screen.getByRole("button", { name: "Start session" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Join session" })).toBeDisabled();
    expect(screen.getByRole("textbox", { name: "Pairing code" })).toBeDisabled();
  });

  it("shows the waiting code, QR value, join link, and peer counts", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async () => {});
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    const { controller } = renderPanel("presenter", connectedState("waiting"));

    const joinUrl = `${window.location.origin}/present?pair=ABC123`;
    const qr = screen.getByLabelText("Pairing QR code");
    expect(screen.getByText("ABC123")).toBeInTheDocument();
    expect(qr).toHaveAttribute("data-qr-value", joinUrl);
    expect(screen.getByRole("link", { name: "Copyable join URL" })).toHaveAttribute(
      "href",
      joinUrl,
    );
    expect(screen.getByText("1 presenter · 2 audiences")).toBeInTheDocument();
    expect(controller.startSession).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Copy join link" }));
    expect(writeText).toHaveBeenCalledWith(joinUrl);
    expect(screen.getByText("Join link copied")).toBeInTheDocument();
  });

  it("uses the presenter route when an audience device shares its join URL", () => {
    renderPanel("audience", connectedState("waiting"));

    const joinUrl = `${window.location.origin}/presenter?pair=ABC123`;
    expect(screen.getByLabelText("Pairing QR code")).toHaveAttribute(
      "data-qr-value",
      joinUrl,
    );
    expect(screen.getByRole("link", { name: "Copyable join URL" })).toHaveAttribute(
      "href",
      joinUrl,
    );
  });

  it("uses concise connected and reconnecting status copy", () => {
    const { rerender } = renderPanel("audience", connectedState("connected"));
    expect(screen.getByRole("status", { name: "Connected" })).toBeInTheDocument();

    rerender(
      <PresentationPairingPanel
        role="audience"
        controller={controllerFor(connectedState("reconnecting"))}
      />,
    );
    expect(screen.getByRole("status", { name: "Reconnecting" })).toBeInTheDocument();
  });

  it("offers retry for a retryable failure", async () => {
    const user = userEvent.setup();
    const controller = controllerFor({
      kind: "failed",
      message: "The pairing server is unavailable.",
      retryable: true,
    });
    render(<PresentationPairingPanel role="audience" controller={controller} />);

    expect(screen.getByText("The pairing server is unavailable.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry pairing" }));
    expect(controller.retry).toHaveBeenCalledOnce();
  });

  it("explains an ended session", () => {
    renderPanel("audience", { kind: "ended", reason: "presenter_ended" });

    expect(screen.getByRole("status", { name: "Presentation ended" })).toBeInTheDocument();
    expect(screen.getByText("The presenter ended this session.")).toBeInTheDocument();
    expect(screen.queryByLabelText("Pairing QR code")).toBeNull();
  });

  it("requires presenter confirmation before ending the session", async () => {
    const user = userEvent.setup();
    const { controller } = renderPanel("presenter", connectedState());

    await user.click(screen.getByRole("button", { name: "End presentation" }));
    expect(screen.getByText("End presentation for everyone?")).toBeInTheDocument();
    expect(controller.endSession).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "End presentation now" }));
    expect(controller.endSession).toHaveBeenCalledOnce();
  });

  it("does not expose an end action to the audience", () => {
    renderPanel("audience", connectedState());

    expect(screen.queryByRole("button", { name: /End presentation/ })).toBeNull();
  });
});
