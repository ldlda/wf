import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { findBeat, findScene } from "../storyboard.js";
import { ProblemLoopScene } from "./ProblemLoopScene.js";

const problemScene = findScene("problem")!;

afterEach(() => cleanup());

describe("ProblemLoopScene", () => {
  it("shows direct action as a vertical chat and tool transcript", () => {
    render(<ProblemLoopScene scene={problemScene} beat={findBeat("problem", "direct-actions")!} />);

    const transcript = screen.getByRole("list", { name: /one-off tool loop transcript/i });
    expect(within(transcript).getByText("User prompt")).toBeInTheDocument();
    expect(within(transcript).getByText("Agent reasoning")).toBeInTheDocument();
    expect(within(transcript).getByText("Tool call")).toBeInTheDocument();
    expect(within(transcript).getByText("Observation")).toBeInTheDocument();
    expect(within(transcript).getByText("Final answer")).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: /^Action sequence$/i })).not.toBeInTheDocument();
  });

  it("renders reusable automation with simple verbs only", () => {
    render(<ProblemLoopScene scene={problemScene} beat={findBeat("problem", "missing-contracts")!} />);

    const automation = screen.getByRole("group", { name: "Reusable automation" });
    for (const label of ["design", "save", "connect", "run", "inspect"]) {
      expect(within(automation).getByText(label)).toBeInTheDocument();
    }
    for (const formalName of ["Draft", "Artifact", "Deployment", "Trace"]) {
      expect(screen.queryByText(formalName)).not.toBeInTheDocument();
    }
  });

  it("keeps reusable automation as the durable counterpart without formal lifecycle words", () => {
    render(<ProblemLoopScene scene={problemScene} beat={findBeat("problem", "missing-contracts")!} />);

    expect(screen.getByRole("group", { name: /reusable automation/i })).toBeInTheDocument();
    expect(screen.getByText("design")).toBeInTheDocument();
    expect(screen.getByText("save")).toBeInTheDocument();
    expect(screen.getByText("connect")).toBeInTheDocument();
    expect(screen.getByText("run")).toBeInTheDocument();
    expect(screen.getByText("inspect")).toBeInTheDocument();
    expect(screen.queryByText("Draft")).not.toBeInTheDocument();
    expect(screen.queryByText("Artifact")).not.toBeInTheDocument();
    expect(screen.queryByText("Deployment")).not.toBeInTheDocument();
    expect(screen.queryByText("Trace")).not.toBeInTheDocument();
  });
});
