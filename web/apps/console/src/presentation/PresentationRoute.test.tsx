import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { PresentationRoute } from "./PresentationRoute.js";

afterEach(() => cleanup());

describe("PresentationRoute", () => {
  it("renders the presentation stage entry point", () => {
    render(<PresentationRoute />);

    expect(screen.getByRole("main", { name: /lda.chat presentation/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Thesis/ })).toBeInTheDocument();
  });

  it("starts from a scene hash and advances with keyboard", async () => {
    window.location.hash = "#scene/agent-handoff/request";
    render(<PresentationRoute />);

    expect(screen.getByRole("heading", { name: /Agent Handoff/i })).toBeInTheDocument();

    await userEvent.keyboard("{ArrowRight}");
    expect(await screen.findByText(/The interface delegates durable work to lda\.chat/i)).toBeInTheDocument();
  });

  it("renders replay-first chat, beat rail, and stage caption", () => {
    render(<PresentationRoute />);

    expect(screen.getByText("Prepare the thesis readiness report.")).toBeInTheDocument();
    expect(screen.getByLabelText(/presentation scene rail/i)).toBeInTheDocument();
    expect(screen.getByText("Replay · running")).toBeInTheDocument();
  });

  it("shows node spotlight when a graph node is selected", async () => {
    window.location.hash = "#scene/workflow-demo/graph";
    render(<PresentationRoute />);
    await userEvent.click(screen.getByRole("button", { name: /issue review/i }));

    expect(screen.getByRole("dialog", { name: /issue review/i })).toBeInTheDocument();
    expect(screen.getByText("Workflow node")).toBeInTheDocument();
  });

  it("can advance replay far enough to show a product operation block", async () => {
    window.location.hash = "#scene/workflow-demo/operation";
    render(<PresentationRoute />);

    expect(await screen.findByText(/workflow.runs.start/i)).toBeInTheDocument();
  });

  it("shows resume and trace operation blocks for later beats", async () => {
    window.location.hash = "#scene/interrupt-evidence/resume";
    render(<PresentationRoute />);
    expect(await screen.findByText(/workflow.runs.resume/i)).toBeInTheDocument();
  });

  it("runs the prepared agent and applies the interrupt node action", async () => {
    render(<PresentationRoute />);

    await userEvent.click(screen.getByRole("button", { name: /run prepared agent/i }));

    expect(await screen.findByText(/prepared workflow recipe/i)).toBeInTheDocument();
    expect(screen.getAllByText(/selectWorkflowNode/i).length).toBeGreaterThanOrEqual(2);
    expect(await screen.findByRole("dialog", { name: /issue review/i })).toBeInTheDocument();
  });

  it("opens a positioning branch and returns to the exact originating beat", async () => {
    window.location.hash = "#scene/positioning/lda-position";
    render(<PresentationRoute />);

    await userEvent.click(screen.getByRole("button", { name: /open discussion topics/i }));
    await userEvent.click(screen.getByRole("button", { name: /hosted automation/i }));
    expect(window.location.hash).toBe("#discuss/hosted-automation");

    await userEvent.click(screen.getByRole("button", { name: /return to positioning/i }));
    expect(window.location.hash).toBe("#scene/positioning/lda-position");
  });

  it("uses the parent scene as return location for a directly linked branch", async () => {
    window.location.hash = "#discuss/mcp-agent-scale";
    render(<PresentationRoute />);
    await userEvent.click(screen.getByRole("button", { name: /return to positioning/i }));
    expect(window.location.hash).toBe("#scene/positioning/landscape");
  });
});
