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

describe("AgentHandoffScene", () => {
  afterEach(cleanup);

  it("renders a log region named prepared authoring conversation", () => {
    renderBeat("request");
    expect(screen.getByRole("log", { name: "prepared authoring conversation" })).toBeInTheDocument();
  });

  it("renders separated user and assistant turns on the request beat", () => {
    renderBeat("request");
    const userMessages = screen.getAllByText(/report|workflow|prepare/i);
    expect(userMessages.length).toBeGreaterThanOrEqual(1);
    const assistantMessages = screen.getAllByText(/inspect|capabilities|sources|schemas|let me/i);
    expect(assistantMessages.length).toBeGreaterThanOrEqual(1);
  });

  it("renders the full conversation on the handoff beat", () => {
    renderBeat("handoff");
    const userMessages = screen.getAllByText(/report|workflow|prepare|save/i);
    expect(userMessages.length).toBeGreaterThanOrEqual(1);
    const assistantMessages = screen.getAllByText(/inspect|sources|capabilities|compile|deployment|artifact/i);
    expect(assistantMessages.length).toBeGreaterThanOrEqual(2);
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
  });

  it("does not include prepared workflow lifecycle content on handoff", () => {
    renderBeat("handoff");
    expect(screen.queryByText("prepared workflow lifecycle")).not.toBeInTheDocument();
  });
});
