import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { demoBeatLensForBeat } from "./demo-workflow-model.js";
import { DemoContinuityRail } from "./DemoContinuityRail.js";

afterEach(() => cleanup());

describe("DemoContinuityRail", () => {
  it("renders the four-step product story spine", () => {
    render(<DemoContinuityRail lens={demoBeatLensForBeat("approval")} />);

    const rail = screen.getByLabelText("demo continuity");
    expect(within(rail).getByText("Agent request")).toBeInTheDocument();
    expect(within(rail).getByText("Workflow run")).toBeInTheDocument();
    expect(within(rail).getByText("Human boundary")).toBeInTheDocument();
    expect(within(rail).getByText("Evidence")).toBeInTheDocument();
  });

  it("marks the current phase and shows the current proof label", () => {
    render(<DemoContinuityRail lens={demoBeatLensForBeat("resume")} />);

    expect(screen.getByText("workflow.runs.resume")).toBeInTheDocument();
    expect(screen.getByText("Human boundary").closest("[data-active]")).toHaveAttribute(
      "data-active",
      "false",
    );
    expect(screen.getByText("Evidence").closest("[data-active]")).toHaveAttribute(
      "data-active",
      "false",
    );
    expect(screen.getByText("Workflow run").closest("[data-active]")).toHaveAttribute(
      "data-completed",
      "true",
    );
  });
});
