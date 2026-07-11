import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { findBeat, findScene } from "../storyboard.js";
import { AgentHandoffScene } from "./AgentHandoffScene.js";
import { SCENE8_REQUEST } from "./scene8-entry-state.js";

const renderRequestBeat = () => {
  const scene = findScene("agent-handoff");
  const beat = findBeat("agent-handoff", "request");
  if (!scene || !beat) throw new Error("missing agent-handoff/request");
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

    expect(screen.getByRole("region", { name: "prepared agent request" })).toHaveAttribute(
      "data-handoff-phase",
      "discover",
    );
    expect(screen.getByRole("region", { name: "prepared agent request" })).toHaveAttribute(
      "data-presentation-surface",
      "editorial",
    );
    expect(screen.getByRole("heading", { name: /what should the workflow author prepare/i })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /authoring request/i })).toHaveValue(SCENE8_REQUEST);
    expect(screen.queryByRole("list", { name: "prepared handoff phases" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /run prepared workflow/i })).not.toBeInTheDocument();
  });

  it("reveals separated user and assistant turns after local submission", async () => {
    renderRequestBeat();
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(screen.getAllByText(/report|workflow|prepare/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/inspect|capabilities|sources|schemas|let me/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole("button", { name: /discover.*4 tool calls/i })).toBeInTheDocument();
  });

  it("does not render prepared workflow lifecycle content", () => {
    renderRequestBeat();
    expect(screen.queryByText("prepared workflow lifecycle")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /run prepared workflow/i })).not.toBeInTheDocument();
  });
});
