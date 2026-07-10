import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
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
    expect(screen.getByText("Validate")).toBeInTheDocument();
    expect(screen.getAllByText(/diagnos|repair/i).length).toBeGreaterThanOrEqual(1);
  });

  it("artifact shows immutable ID and version", () => {
    renderBeat("artifact");
    expect(screen.getByText("Artifact")).toBeInTheDocument();
    expect(screen.getByText(/art_x9y8z7/i)).toBeInTheDocument();
  });

  it("deployment shows bindings and validation", () => {
    renderBeat("deployment");
    expect(screen.getByText("Deployment")).toBeInTheDocument();
    expect(screen.getByText(/dep_m4n5p6/i)).toBeInTheDocument();
  });

  it("renders an Agent trace trigger", () => {
    renderBeat("discover");
    expect(screen.getByRole("button", { name: "Agent trace" })).toBeInTheDocument();
  });

  it("trace is initially closed", () => {
    renderBeat("discover");
    expect(screen.queryByRole("dialog", { name: "Authoring trace" })).not.toBeInTheDocument();
  });

  it("opens the trace panel when Agent trace is clicked", async () => {
    const user = userEvent.setup();
    renderBeat("draft");
    await user.click(screen.getByRole("button", { name: "Agent trace" }));
    expect(screen.getByRole("dialog", { name: "Authoring trace" })).toBeInTheDocument();
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
});
