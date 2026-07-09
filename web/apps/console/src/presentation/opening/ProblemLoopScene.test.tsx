import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { findBeat, findScene } from "../storyboard.js";
import { ProblemLoopScene } from "./ProblemLoopScene.js";

const problemScene = findScene("problem")!;

afterEach(() => cleanup());

describe("ProblemLoopScene", () => {
  it("renders the action sequence as useful but insufficient", () => {
    render(<ProblemLoopScene scene={problemScene} beat={findBeat("problem", "direct-actions")!} />);

    const action = screen.getByRole("group", { name: "Action sequence" });
    expect(within(action).getByText("think")).toBeInTheDocument();
    expect(within(action).getAllByText("tool")).toHaveLength(2);
    expect(within(action).getByText("observe")).toBeInTheDocument();
    expect(within(action).getByText("done")).toBeInTheDocument();
    expect(screen.getByText(/useful once/i)).toBeInTheDocument();
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
});
