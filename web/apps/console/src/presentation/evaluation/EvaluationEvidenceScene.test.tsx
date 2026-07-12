import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { EvaluationEvidenceScene } from "./EvaluationEvidenceScene.js";

const scene = {
  id: "evaluation",
  number: 13,
  title: "Evaluation",
  claimClass: "evaluated" as const,
  evidencePointer: "Thesis Evaluation and Appendix C",
  view: "evaluation" as const,
  beats: [],
};

const beat = (id: string) => ({
  id,
  title: id,
  caption: `Caption for ${id}`,
  chatMode: "hidden" as const,
  chatTheme: "light" as const,
  evidencePresentation: "hidden" as const,
  figure: null,
});

afterEach(() => cleanup());

describe("EvaluationEvidenceScene", () => {
  it.each(["cohort", "validity", "findings"])("renders the persistent board for %s", (beatId) => {
    render(<EvaluationEvidenceScene scene={scene} beat={beat(beatId)} />);
    const board = screen.getByRole("group", { name: /evaluation evidence board/i });
    expect(board).toHaveAttribute("data-visual-role", "evaluation-summary");
    expect(board).toHaveAttribute("data-presentation-surface", "editorial");
    expect(board).toHaveAttribute(
      "data-evaluation-beat",
      beatId,
    );
    expect(board).toHaveAttribute(
      "data-evaluation-focus",
      beatId,
    );
    expect(screen.getByText("36")).toBeInTheDocument();
    expect(screen.getByText("27")).toBeInTheDocument();
    expect(screen.getByText("8")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("renders the manual audit reconciliation and validity statement", () => {
    render(<EvaluationEvidenceScene scene={scene} beat={beat("validity")} />);
    expect(screen.getByText("7 automatic successes")).toBeInTheDocument();
    expect(screen.getByText("invalid as clean evidence")).toBeInTheDocument();
    expect(screen.getByText("3 automatic failures")).toBeInTheDocument();
    expect(screen.getByText("accepted from saved evidence")).toBeInTheDocument();
    expect(
      screen.getByText("Bounded longitudinal engineering evidence, not a controlled model comparison."),
    ).toBeInTheDocument();
  });

  it("renders six labelled finding icons without ranking language", () => {
    render(<EvaluationEvidenceScene scene={scene} beat={beat("findings")} />);
    const findings = screen.getByRole("list", { name: /ux gaps exposed by trials/i });
    expect(findings.querySelectorAll("svg")).toHaveLength(6);
    for (const label of [
      "Schema discovery",
      "Repair hints",
      "Binding commands",
      "Output schemas",
      "Shell assumptions",
      "Source contamination",
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    expect(findings.textContent).not.toMatch(/%|success rate|leaderboard/i);
  });
});
