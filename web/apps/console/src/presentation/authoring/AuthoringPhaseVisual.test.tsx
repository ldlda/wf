import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import {
  projectPreparedLifecycleStep,
  type PreparedLifecycleStepId,
} from "./authoring-projection.js";
import { AuthoringPhaseVisual } from "./AuthoringPhaseVisual.js";

afterEach(cleanup);

const renderStep = (step: PreparedLifecycleStepId) =>
  render(<AuthoringPhaseVisual projection={projectPreparedLifecycleStep(step)} />);

describe("AuthoringPhaseVisual", () => {
  it.each([
    ["discover", "inventory", "source inventory result"],
    ["draft", "draft", "draft structure result"],
    ["diagnose", "diagnostic", "draft validation diagnostic"],
    ["repair", "repair", "route repair result"],
    ["artifact", "artifact", "immutable artifact result"],
    ["deployment", "deployment", "runnable deployment result"],
  ] as const)("renders %s as a factual %s result", (step, kind, label) => {
    renderStep(step);
    expect(screen.getByRole("region", { name: label })).toHaveAttribute(
      "data-authoring-result",
      kind,
    );
  });

  it.each([
    ["discover", "inventory"],
    ["draft", "workflow-draft"],
    ["diagnose", "workflow-diagnostic"],
    ["repair", "workflow-repair"],
    ["artifact", "artifact"],
    ["deployment", "deployment"],
  ] as const)("makes the %s diagram primary", (step, diagramKind) => {
    renderStep(step);

    expect(screen.getByTestId("authoring-primary-diagram")).toHaveAttribute(
      "data-diagram-kind",
      diagramKind,
    );
  });

  it("renders total inventory separately from configured local sources", () => {
    renderStep("discover");
    const result = screen.getByRole("region", { name: /source inventory result/i });

    expect(within(result).getByText("6 total inventory sources")).toBeInTheDocument();
    expect(within(result).getByRole("heading", { name: "Configured local sources (3)" })).toBeInTheDocument();
    expect(within(result).getByText("local.lda_docs")).toBeInTheDocument();
    expect(within(result).getByText("local.lda_report")).toBeInTheDocument();
    expect(within(result).getByText("local.issue_board")).toBeInTheDocument();
    expect(within(result).queryByText(/^6 configured local sources$/)).not.toBeInTheDocument();
  });

  it("renders the draft revision, steps, and routes", () => {
    renderStep("draft");
    const result = screen.getByRole("region", { name: /draft structure result/i });

    expect(within(result).getByText("Revision 2")).toBeInTheDocument();
    expect(within(result).getByText("read_documents")).toBeInTheDocument();
    expect(within(result).getByText("analyze")).toBeInTheDocument();
    expect(within(result).getByText("read_documents.ok -> analyze")).toBeInTheDocument();
    expect(within(result).getByText("analyze.ok -> __end__")).toBeInTheDocument();
  });

  it("renders the reviewed draft validation diagnostic", () => {
    renderStep("diagnose");
    const result = screen.getByRole("region", { name: /draft validation diagnostic/i });

    expect(result).toHaveAttribute("data-authoring-result", "diagnostic");
    expect(within(result).getByText("missing_outcome_edge")).toBeInTheDocument();
    expect(within(result).getByText("nodes[analyze]")).toBeInTheDocument();
    expect(within(result).getByText(/missing edges for outcomes.*ok/i)).toBeInTheDocument();
    expect(within(result).getByText(/cannot prove where execution goes next/i)).toBeInTheDocument();
    expect(within(result).getByText("Revision 3")).toBeInTheDocument();
    expect(within(result).getByRole("note", { name: /prepared fault injection/i })).toHaveTextContent(
      "wf draft remove-route lda_report_workflow --revision 2 --step analyze --outcome ok",
    );
  });

  it("renders route repair as a valid revision with compact prior context", () => {
    renderStep("repair");
    const result = screen.getByRole("region", { name: /route repair result/i });
    const prior = within(result).getByRole("note", { name: /prior validation diagnostic/i });

    expect(within(result).getByText("wf draft set-route lda_report_workflow --revision 3 --step analyze --outcome ok --to __end__")).toBeInTheDocument();
    expect(within(result).getAllByText("Valid")).toHaveLength(2);
    expect(within(result).getByText("Revision 4")).toBeInTheDocument();
    expect(within(result).getByText("0 diagnostics")).toBeInTheDocument();
    expect(within(prior).getByText(/reachable node is missing edges for outcomes.*ok/i)).toBeInTheDocument();
    expect(result.querySelector("[data-result-primary='true']")).toContainElement(
      within(result).getByText(/set-route/),
    );
  });

  it("renders immutable artifact identity and required sources", () => {
    renderStep("artifact");
    const result = screen.getByRole("region", { name: /immutable artifact result/i });

    expect(within(result).getByText("lda_report_case_study")).toBeInTheDocument();
    expect(within(result).getByText("Version 1")).toBeInTheDocument();
    expect(within(result).getByText("Immutable")).toBeInTheDocument();
    expect(within(result).getByText("local.lda_docs")).toBeInTheDocument();
    expect(within(result).getByText("local.lda_report")).toBeInTheDocument();
    expect(within(result).getByText("local.issue_board")).toBeInTheDocument();
  });

  it("renders runnable deployment identity and bindings", () => {
    renderStep("deployment");
    const result = screen.getByRole("region", { name: /runnable deployment result/i });

    expect(within(result).getByText("lda_report_case_study.default")).toBeInTheDocument();
    expect(within(result).getByText("Runnable")).toBeInTheDocument();
    expect(within(result).getAllByText("local.lda_docs")).toHaveLength(2);
    expect(within(result).getAllByText("local.lda_report")).toHaveLength(2);
    expect(within(result).getAllByText("local.issue_board")).toHaveLength(2);
  });
});
