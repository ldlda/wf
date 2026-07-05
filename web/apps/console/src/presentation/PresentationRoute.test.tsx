import { act, cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, describe, expect, it } from "vitest";

class MockResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

beforeAll(() => {
  globalThis.ResizeObserver = MockResizeObserver as unknown as typeof ResizeObserver;
  globalThis.DOMRect = {
    fromRect: () => ({
      x: 0,
      y: 0,
      width: 0,
      height: 0,
      top: 0,
      right: 0,
      bottom: 0,
      left: 0,
      toJSON() {},
    }),
  } as unknown as typeof DOMRect;
});

afterEach(() => cleanup());

describe("PresentationRoute", () => {
  it("renders stable chat, primary, progress, and transient evidence surfaces", async () => {
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);
    expect(screen.getByLabelText(/agent chat region/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/primary presentation region/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/presentation footer/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/evidence region/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("dialog", { name: /evidence inspector/i })).not.toBeInTheDocument();
  });

  it("shows a receipt without auto-opening evidence on an evidence beat", async () => {
    window.location.hash = "#scene/interrupt-evidence/trace";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);
    expect(await screen.findByRole("button", { name: /inspect evidence/i })).toBeInTheDocument();
    expect(screen.queryByRole("dialog", { name: /evidence inspector/i })).not.toBeInTheDocument();
  });

  it("opens the inspector from an explicit operation action", async () => {
    const user = userEvent.setup();
    window.location.hash = "#scene/workflow-demo/operation";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);
    await user.click(await screen.findByRole("button", { name: /view raw evidence/i }));
    expect(screen.getByRole("dialog", { name: /evidence inspector/i })).toBeInTheDocument();
  });

  it("closes the inspector when navigation moves to another beat", async () => {
    const user = userEvent.setup();
    window.location.hash = "#scene/workflow-demo/operation";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);
    await user.click(await screen.findByRole("button", { name: /view raw evidence/i }));
    expect(screen.getByRole("dialog", { name: /evidence inspector/i })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /close evidence/i }));
    expect(screen.queryByRole("dialog", { name: /evidence inspector/i })).not.toBeInTheDocument();
  });
});
