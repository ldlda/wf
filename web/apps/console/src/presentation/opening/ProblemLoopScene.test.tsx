import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { findBeat, findScene } from "../storyboard.js";
import { ProblemLoopScene } from "./ProblemLoopScene.js";

const problemScene = findScene("problem")!;

afterEach(() => cleanup());

describe("ProblemLoopScene", () => {
  it("uses the assistant transcript surface for the direct-action side", async () => {
    render(<ProblemLoopScene scene={problemScene} beat={findBeat("problem", "direct-actions")!} />);

    const transcript = screen.getByRole("log", { name: /one-off assistant transcript/i });
    expect(transcript).toHaveClass("assistant-operator-thread");
    expect(within(transcript).getByText("Can you finish this workspace task?")).toBeInTheDocument();
    const toolButtons = within(transcript).getAllByRole("button", { name: /workflow.run_once/i });
    expect(toolButtons).toHaveLength(3);
    expect(within(transcript).getByText("Done. But none of this is recorded in a durable workflow.")).toBeInTheDocument();
  });

  it("renders reusable automation as a durable workflow blueprint", () => {
    render(<ProblemLoopScene scene={problemScene} beat={findBeat("problem", "missing-contracts")!} />);

    const blueprint = screen.getByRole("group", { name: /durable workflow blueprint/i });
    expect(blueprint).toHaveAttribute("data-blueprint-active", "true");

    for (const label of ["design", "save", "connect", "run", "inspect"]) {
      expect(within(blueprint).getByText(label)).toBeInTheDocument();
    }

    expect(within(blueprint).getByText("schemas")).toBeInTheDocument();
    expect(within(blueprint).getByText("bindings")).toBeInTheDocument();
    expect(within(blueprint).getByText("records")).toBeInTheDocument();
  });

  it("keeps Scene 2 body out of formal lifecycle vocabulary", () => {
    render(<ProblemLoopScene scene={problemScene} beat={findBeat("problem", "missing-contracts")!} />);

    for (const formalName of ["Draft", "Artifact", "Deployment", "Trace"]) {
      expect(screen.queryByText(formalName)).not.toBeInTheDocument();
    }
  });
});
