import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { PresentationRoute } from "./PresentationRoute.js";

afterEach(() => cleanup());

describe("PresentationRoute", () => {
  it("renders the presentation stage entry point", () => {
    render(<PresentationRoute />);

    expect(screen.getByRole("main", { name: /lda.chat presentation/i })).toBeInTheDocument();
    expect(screen.getByText(/External planners propose actions/i)).toBeInTheDocument();
  });

  it("starts from a hash beat and advances with keyboard", async () => {
    window.location.hash = "#interrupt-approval";
    render(<PresentationRoute />);

    expect(screen.getByText(/Human approval is a typed workflow boundary/i)).toBeInTheDocument();

    window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight" }));
    expect(await screen.findByText(/Resuming commits the approved branch/i)).toBeInTheDocument();
  });

  it("renders replay-first chat, beat rail, and stage caption", () => {
    render(<PresentationRoute />);

    expect(screen.getByText("Prepare the thesis readiness report.")).toBeInTheDocument();
    expect(screen.getByLabelText(/presentation beat rail/i)).toBeInTheDocument();
    expect(screen.getByText("Replay · running")).toBeInTheDocument();
  });

  it("shows node spotlight when a graph node is selected", async () => {
    render(<PresentationRoute />);
    await userEvent.click(screen.getByRole("button", { name: /issue review/i }));

    expect(screen.getByRole("dialog", { name: /issue review/i })).toBeInTheDocument();
    expect(screen.getByText("NodeUse")).toBeInTheDocument();
  });

  it("can advance replay far enough to show a product operation block", async () => {
    render(<PresentationRoute />);
    await userEvent.click(screen.getByRole("button", { name: /product operation/i }));

    expect(await screen.findByText(/workflow.runs.start/i)).toBeInTheDocument();
  });

  it("shows resume and trace operation blocks for later beats", async () => {
    render(<PresentationRoute />);

    await userEvent.click(screen.getByRole("button", { name: /resume output/i }));
    expect(await screen.findByText(/workflow.runs.resume/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /trace evidence/i }));
    expect(await screen.findByText(/workflow.runs.trace/i)).toBeInTheDocument();
  });
});
