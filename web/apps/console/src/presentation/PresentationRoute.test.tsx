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

  it("renders audience progress chrome without rail or mode label", () => {
    render(<PresentationRoute />);

    expect(screen.getByText("Prepare the thesis readiness report.")).toBeInTheDocument();
    expect(screen.queryByLabelText(/presentation scene rail/i)).not.toBeInTheDocument();
    expect(screen.getByLabelText("scene position")).toBeInTheDocument();
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

  it("opens a positioning branch via hash and returns to the parent scene first beat", async () => {
    window.location.hash = "#discuss/hosted-automation";
    render(<PresentationRoute />);

    expect(await screen.findByRole("button", { name: /return to positioning/i })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /return to positioning/i }));
    expect(window.location.hash).toBe("#scene/positioning/landscape");
  });

  it("uses the parent scene as return location for a directly linked branch", async () => {
    window.location.hash = "#discuss/mcp-agent-scale";
    render(<PresentationRoute />);
    await userEvent.click(screen.getByRole("button", { name: /return to positioning/i }));
    expect(window.location.hash).toBe("#scene/positioning/landscape");
  });

  it("renders stable chat, primary, evidence, and progress regions", () => {
    render(<PresentationRoute />);
    expect(screen.getByLabelText(/agent chat region/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/primary presentation region/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/evidence region/i)).toBeInTheDocument();
    expect(screen.getByLabelText("scene position")).toBeInTheDocument();
  });
});
