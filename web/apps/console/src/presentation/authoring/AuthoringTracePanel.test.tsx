import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthoringTracePanel } from "./AuthoringTracePanel.js";
import { type AuthoringPhaseId } from "./authoring-recording.js";

afterEach(() => cleanup());

const renderPanel = (
  phase: AuthoringPhaseId,
  open = true,
  onOpen = vi.fn(),
  onClose = vi.fn(),
) => render(
  <AuthoringTracePanel phase={phase} open={open} onOpen={onOpen} onClose={onClose} />,
);

describe("AuthoringTracePanel", () => {
  it("renders an Agent trace trigger", () => {
    renderPanel("discover", false);
    expect(screen.getByRole("button", { name: "Agent trace" })).toBeInTheDocument();
  });

  it("calls onOpen when trigger is clicked", async () => {
    const user = userEvent.setup();
    const onOpen = vi.fn();
    renderPanel("discover", false, onOpen);
    await user.click(screen.getByRole("button", { name: "Agent trace" }));
    expect(onOpen).toHaveBeenCalledTimes(1);
  });

  it("shows the dialog overlay when open is true", () => {
    renderPanel("discover", true);
    expect(screen.getByRole("dialog", { name: "Authoring trace" })).toBeInTheDocument();
  });

  it("hides the dialog overlay when open is false", () => {
    renderPanel("discover", false);
    expect(screen.queryByRole("dialog", { name: "Authoring trace" })).not.toBeInTheDocument();
  });

  it("renders the selected phase expanded in the dialog", () => {
    renderPanel("draft", true);
    expect(screen.getByText("Draft")).toBeInTheDocument();
  });

  it("renders all five phases in the panel", () => {
    renderPanel("discover", true);
    expect(screen.getByText("Discover")).toBeInTheDocument();
    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(screen.getByText("Validate")).toBeInTheDocument();
    expect(screen.getByText("Artifact")).toBeInTheDocument();
    expect(screen.getByText("Deployment")).toBeInTheDocument();
  });

  it("renders command blocks in the selected phase", () => {
    renderPanel("validate", true);
    const commands = screen.getAllByText(/wf bind|wf validate/i);
    expect(commands.length).toBeGreaterThanOrEqual(1);
  });

  it("closes the dialog when Escape is pressed", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<AuthoringTracePanel phase="discover" open={true} onOpen={vi.fn()} onClose={onClose} />);
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("closes the dialog when backdrop is clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<AuthoringTracePanel phase="discover" open={true} onOpen={vi.fn()} onClose={onClose} />);
    const backdrop = document.querySelector(".authoring-trace-panel__backdrop");
    expect(backdrop).toBeInTheDocument();
    await user.click(backdrop!);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("restores focus to the trigger after closing", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const { rerender } = render(
      <AuthoringTracePanel phase="discover" open={true} onOpen={vi.fn()} onClose={onClose} />,
    );
    await user.keyboard("{Escape}");
    rerender(
      <AuthoringTracePanel phase="discover" open={false} onOpen={vi.fn()} onClose={onClose} />,
    );
    expect(screen.getByRole("button", { name: "Agent trace" })).toHaveFocus();
  });
});
