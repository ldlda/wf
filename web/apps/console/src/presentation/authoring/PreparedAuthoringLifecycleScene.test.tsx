import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { findBeat, findScene } from "../storyboard.js";
import { PreparedAuthoringLifecycleScene } from "./PreparedAuthoringLifecycleScene.js";

afterEach(() => cleanup());

const renderBeat = (beatId: string) => {
  const scene = findScene("prepared-lifecycle");
  const beat = findBeat("prepared-lifecycle", beatId);
  if (!scene || !beat) throw new Error(`missing prepared-lifecycle/${beatId}`);
  return render(<PreparedAuthoringLifecycleScene scene={scene} beat={beat} />);
};

describe("PreparedAuthoringLifecycleScene", () => {
  it("discover shows sources, capabilities, and schema", () => {
    renderBeat("discover");
    expect(screen.getByRole("region", { name: "prepared workflow authoring lifecycle" })).toHaveAttribute(
      "data-presentation-surface",
      "editorial",
    );
    expect(screen.getByText("Discover")).toBeInTheDocument();
    expect(screen.getAllByText(/sources|capabilities|schema/i).length).toBeGreaterThanOrEqual(1);
  });

  it("draft shows graph or routes", () => {
    renderBeat("draft");
    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(screen.getAllByText(/graph|routes/i).length).toBeGreaterThanOrEqual(1);
  });

  it("validate shows diagnosis and repair", () => {
    renderBeat("validate");
    expect(screen.getByRole("region", { name: "prepared workflow authoring lifecycle" })).toHaveAttribute(
      "data-presentation-surface",
      "editorial",
    );
    expect(screen.getByText("Validate")).toBeInTheDocument();
    expect(screen.getAllByText(/diagnos|repair/i).length).toBeGreaterThanOrEqual(1);
  });

  it("artifact shows immutable ID and version", () => {
    renderBeat("artifact");
    expect(screen.getByText("Artifact")).toBeInTheDocument();
    expect(screen.getAllByText(/lda_report_case_study/i).length).toBeGreaterThanOrEqual(1);
  });

  it("deployment shows bindings and validation", () => {
    renderBeat("deployment");
    expect(screen.getAllByText("Deployment").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/lda_report_case_study\.default/i).length).toBeGreaterThanOrEqual(1);
  });

  it.each([
    ["discover", "discovery evidence"],
    ["draft", "draft graph evidence"],
    ["validate", "validation repair evidence"],
    ["artifact", "artifact evidence"],
    ["deployment", "deployment binding evidence"],
  ] as const)("renders %s as the primary phase visual", (beatId, label) => {
    renderBeat(beatId);
    expect(screen.getByRole("region", { name: label })).toBeInTheDocument();
  });

  it("keeps the assistant and dominant phase visual visible as stable siblings", () => {
    renderBeat("draft");

    const workspace = screen.getByRole("region", { name: "prepared workflow authoring lifecycle" });
    const assistant = screen.getByRole("complementary", { name: /prepared authoring assistant/i });
    const visual = screen.getByRole("region", { name: "draft graph evidence" });

    expect(workspace).toContainElement(assistant);
    expect(workspace).toContainElement(visual);
    expect(assistant).toHaveAttribute("data-phase", "draft");
    expect(assistant).toHaveAttribute("data-surface", "prepared-replay");
    expect(assistant.querySelector('[data-surface="stage"]')).toBeInTheDocument();
    expect(workspace.querySelector(".prepared-lifecycle-scene__dock")).not.toBeInTheDocument();
    expect(workspace.querySelector("[role='dialog']")).not.toBeInTheDocument();
    expect(workspace.querySelector("[aria-label='authoring phase rail']"))
      .toBeInTheDocument();
    expect(visual).toHaveAttribute("data-presentation-surface", "editorial");
    expect(visual).toHaveAttribute("data-visual-role", "authoring-phase");
  });

  it("synchronizes the assistant phase, active group, rail, and visual", () => {
    renderBeat("validate");

    expect(screen.getByRole("complementary", { name: /prepared authoring assistant/i }))
      .toHaveAttribute("data-phase", "validate");
    expect(screen.getByRole("button", { name: /validate.*2 tool calls/i }))
      .toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: /draft.*3 tool calls/i }))
      .toHaveAttribute("aria-expanded", "false");
    expect(screen.getByLabelText("authoring phase rail").querySelector("[data-active='true']"))
      .toHaveTextContent("Validate");
    const chat = screen.getByRole("log", { name: "prepared authoring conversation" });
    expect(chat).toHaveAttribute("data-surface", "stage");
    expect(screen.getByRole("region", { name: "validation repair evidence" })).toHaveAttribute(
      "data-presentation-surface",
      "editorial",
    );
  });

  it("does not render the obsolete trace modal or receipt", () => {
    renderBeat("validate");
    expect(screen.queryByRole("button", { name: "Agent trace" })).not.toBeInTheDocument();
    expect(screen.queryByRole("dialog", { name: "Authoring trace" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("prepared authoring receipt")).not.toBeInTheDocument();
  });

  it("renders a compact orientation rail", () => {
    renderBeat("artifact");
    const rail = screen.getByLabelText("authoring phase rail");
    expect(rail).toBeInTheDocument();
    expect(rail.children.length).toBeGreaterThanOrEqual(5);
  });

  it("highlights the active phase in the rail", () => {
    renderBeat("deployment");
    const rail = screen.getByLabelText("authoring phase rail");
    const active = rail.querySelector("[data-active='true']");
    expect(active).toBeInTheDocument();
    expect(active).toHaveTextContent("Deployment");
  });

  it("falls back to discovery for an unexpected storyboard beat", () => {
    const scene = findScene("prepared-lifecycle")!;
    const knownBeat = findBeat("prepared-lifecycle", "discover")!;
    const unexpectedBeat = { ...knownBeat, id: "unexpected" };

    render(<PreparedAuthoringLifecycleScene scene={scene} beat={unexpectedBeat} />);

    expect(screen.getByRole("region", { name: "discovery evidence" })).toBeInTheDocument();
    expect(screen.getByLabelText("authoring phase rail").querySelector("[data-active='true']"))
      .toHaveTextContent("Discover");
  });
});
