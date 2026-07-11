import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { findBeat, findScene } from "../storyboard.js";
import { AgentHandoffScene } from "./AgentHandoffScene.js";

const renderBeat = (beatId: "request" | "handoff") => {
  const scene = findScene("agent-handoff");
  const beat = findBeat("agent-handoff", beatId);
  if (!scene || !beat) throw new Error(`missing agent-handoff/${beatId}`);
  return render(<AgentHandoffScene scene={scene} beat={beat} />);
};

afterEach(cleanup);

describe("AgentHandoffScene", () => {
  it("renders one prepared conversation with a phase orientation rail", () => {
    render(
      <AgentHandoffScene
        scene={findScene("agent-handoff")!}
        beat={findBeat("agent-handoff", "request")!}
      />,
    );

    expect(screen.getByRole("region", { name: "prepared agent handoff" })).toHaveAttribute(
      "data-handoff-phase",
      "discover",
    );
    expect(screen.getByRole("log", { name: "prepared authoring conversation" })).toHaveAttribute(
      "data-surface",
      "stage",
    );
    expect(screen.getByRole("list", { name: "prepared handoff phases" })).toBeInTheDocument();
    expect(screen.getAllByText(/workflow\.sources\.list/i).length).toBeGreaterThan(0);
  });

  it("advances the same conversation to deployment evidence", () => {
    render(
      <AgentHandoffScene
        scene={findScene("agent-handoff")!}
        beat={findBeat("agent-handoff", "handoff")!}
      />,
    );

    expect(screen.getByRole("region", { name: "prepared agent handoff" })).toHaveAttribute(
      "data-handoff-phase",
      "deployment",
    );
    expect(screen.getAllByText(/workflow\.deployments\.save/i).length).toBeGreaterThan(0);
  });

  it("renders separated user and assistant turns on the request beat", () => {
    renderBeat("request");
    expect(screen.getAllByText(/report|workflow|prepare/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/inspect|capabilities|sources|schemas|let me/i).length).toBeGreaterThanOrEqual(1);
  });

  it("interleaves prepared workflow tool groups with the handoff conversation", () => {
    renderBeat("handoff");
    expect(screen.getAllByText(/workflow\.deployments\.save/i).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /deployment.*2 tool calls/i }))
      .toHaveAttribute("aria-expanded", "true");
  });

  it("does not render prepared workflow lifecycle content", () => {
    renderBeat("request");
    expect(screen.queryByText("prepared workflow lifecycle")).not.toBeInTheDocument();
    cleanup();
    renderBeat("handoff");
    expect(screen.queryByText("prepared workflow lifecycle")).not.toBeInTheDocument();
  });
});
