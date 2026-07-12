import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { projectPreparedAuthoringPhase } from "./authoring-projection.js";
import { AuthoringPhaseVisual } from "./AuthoringPhaseVisual.js";

afterEach(cleanup);

describe("AuthoringPhaseVisual", () => {
  it.each(["discover", "draft", "validate", "artifact", "deployment"] as const)(
    "marks the %s visual as editorial",
    (phase) => {
      render(<AuthoringPhaseVisual projection={projectPreparedAuthoringPhase(phase)} />);
      expect(screen.getByRole("region", { name: /evidence/i })).toHaveAttribute(
        "data-presentation-surface",
        "editorial",
      );
    },
  );

  it("shows source inventory and the inspected contract", () => {
    render(<AuthoringPhaseVisual projection={projectPreparedAuthoringPhase("discover")} />);
    expect(screen.getByRole("region", { name: /discovery evidence/i })).toHaveAttribute(
      "data-presentation-surface",
      "editorial",
    );
    expect(screen.getByText("local.lda_docs")).toBeInTheDocument();
    expect(screen.getByText("local.lda_report")).toBeInTheDocument();
    expect(screen.getByText(/documents.*analysis/i)).toBeInTheDocument();
  });

  it("shows the declared draft graph and outcome route", () => {
    render(<AuthoringPhaseVisual projection={projectPreparedAuthoringPhase("draft")} />);
    expect(screen.getByRole("region", { name: /draft graph evidence/i })).toBeInTheDocument();
    expect(screen.getByText("read_documents")).toBeInTheDocument();
    expect(screen.getByText("analyze")).toBeInTheDocument();
    expect(screen.getByText("ok → end")).toBeInTheDocument();
  });

  it("shows the validation diagnostic and repaired projection", () => {
    render(<AuthoringPhaseVisual projection={projectPreparedAuthoringPhase("validate")} />);
    expect(screen.getByText(/no state projection/i)).toBeInTheDocument();
    expect(screen.getByText("analysis → state.analysis")).toBeInTheDocument();
    expect(screen.getByText(/valid draft/i)).toBeInTheDocument();
  });

  it.each(["diagnose", "repair"] as const)("marks the %s authoring focus", (focus) => {
    render(<AuthoringPhaseVisual projection={projectPreparedAuthoringPhase("validate")} focus={focus} />);
    expect(screen.getByRole("region", { name: /validation repair evidence/i })).toHaveAttribute(
      "data-authoring-focus",
      focus,
    );
  });

  it("shows immutable artifact identity and version", () => {
    render(<AuthoringPhaseVisual projection={projectPreparedAuthoringPhase("artifact")} />);
    expect(screen.getByText("lda_report_case_study")).toBeInTheDocument();
    expect(screen.getByText("Version 1")).toBeInTheDocument();
    expect(screen.getByText(/immutable/i)).toBeInTheDocument();
  });

  it("shows all concrete deployment bindings and validation", () => {
    render(<AuthoringPhaseVisual projection={projectPreparedAuthoringPhase("deployment")} />);
    expect(screen.getAllByText("local.lda_docs")).toHaveLength(2);
    expect(screen.getAllByText("local.lda_report")).toHaveLength(2);
    expect(screen.getAllByText("local.issue_board")).toHaveLength(2);
    expect(screen.getByText(/deployment valid/i)).toBeInTheDocument();
  });
});
