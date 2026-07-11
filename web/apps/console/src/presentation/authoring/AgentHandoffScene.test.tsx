import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { findBeat, findScene } from "../storyboard.js";
import { AgentHandoffScene } from "./AgentHandoffScene.js";
import { SCENE8_REQUEST } from "./scene8-entry-state.js";

const renderBeat = (beatId: "request" | "handoff") => {
  const scene = findScene("agent-handoff");
  const beat = findBeat("agent-handoff", beatId);
  if (!scene || !beat) throw new Error(`missing agent-handoff/${beatId}`);
  return render(<AgentHandoffScene scene={scene} beat={beat} />);
};

afterEach(cleanup);

describe("AgentHandoffScene", () => {
  it("renders the empty request beat as a chat composer", () => {
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
    expect(screen.getByRole("region", { name: "prepared agent handoff" })).toHaveAttribute(
      "data-presentation-surface",
      "editorial",
    );
    expect(screen.getByRole("heading", { name: /what should the workflow author prepare/i })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /authoring request/i })).toHaveValue(SCENE8_REQUEST);
    expect(screen.queryByRole("list", { name: "prepared handoff phases" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /run prepared workflow/i })).not.toBeInTheDocument();
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

  it("reveals separated user and assistant turns after local submission", async () => {
    renderBeat("request");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(screen.getAllByText(/report|workflow|prepare/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/inspect|capabilities|sources|schemas|let me/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole("button", { name: /discover.*4 tool calls/i })).toBeInTheDocument();
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

  it("does not expose a workflow run action", () => {
    renderBeat("handoff");
    expect(screen.queryByRole("button", { name: /run prepared workflow/i })).not.toBeInTheDocument();
  });
});
