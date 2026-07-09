import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { findBeat, findScene } from "../storyboard.js";
import { ProblemLoopScene } from "./ProblemLoopScene.js";

const problemScene = findScene("problem")!;

afterEach(() => cleanup());

describe("ProblemLoopScene", () => {
  it("renders the direct-action side as a chat-style tool transcript", () => {
    render(<ProblemLoopScene scene={problemScene} beat={findBeat("problem", "direct-actions")!} />);

    const transcript = screen.getByRole("list", { name: /one-off chat and tool transcript/i });
    const turns = within(transcript).getAllByRole("listitem");

    expect(turns).toHaveLength(5);
    expect(turns[0]).toHaveAttribute("data-turn-kind", "user");
    expect(turns[1]).toHaveAttribute("data-turn-kind", "assistant");
    expect(turns[2]).toHaveAttribute("data-turn-kind", "tool");
    expect(turns[3]).toHaveAttribute("data-turn-kind", "observation");
    expect(turns[4]).toHaveAttribute("data-turn-kind", "answer");
    expect(within(transcript).getByText("User")).toBeInTheDocument();
    expect(within(transcript).getByText("Tool call")).toBeInTheDocument();
    expect(within(transcript).getByText("Observation")).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: /^Action sequence$/i })).not.toBeInTheDocument();
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