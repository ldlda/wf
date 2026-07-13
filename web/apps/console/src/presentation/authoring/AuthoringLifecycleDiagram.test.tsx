import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { projectPreparedLifecycleStep } from "./authoring-projection.js";
import { AuthoringLifecycleDiagram } from "./AuthoringLifecycleDiagram.js";

afterEach(cleanup);

const renderLifecycle = (step: "discover" | "artifact" | "deployment") => {
  const projection = projectPreparedLifecycleStep(step);
  if (
    projection.evidence.kind !== "inventory"
    && projection.evidence.kind !== "artifact"
    && projection.evidence.kind !== "deployment"
  ) {
    throw new Error(`unexpected evidence for ${step}`);
  }
  return render(<AuthoringLifecycleDiagram evidence={projection.evidence} />);
};

describe("AuthoringLifecycleDiagram", () => {
  it("shows configured sources feeding the discovered capability", () => {
    renderLifecycle("discover");
    const diagram = screen.getByRole("img", { name: /source capability map/i });

    expect(within(diagram).getByText("local.lda_docs")).toBeInTheDocument();
    expect(within(diagram).getByText("local.lda_report")).toBeInTheDocument();
    expect(within(diagram).getByText("local.issue_board")).toBeInTheDocument();
    expect(within(diagram).getByText("local.lda_report.analyze_documents")).toBeInTheDocument();
    expect(diagram).toHaveAttribute("data-lifecycle-diagram", "inventory");
  });

  it("keeps the workflow silhouette and requirements attached to the immutable version", () => {
    renderLifecycle("artifact");
    const diagram = screen.getByRole("img", { name: /versioned artifact map/i });

    expect(within(diagram).getByText("read_documents")).toBeInTheDocument();
    expect(within(diagram).getByText("analyze")).toBeInTheDocument();
    expect(within(diagram).getByText("lda_report_case_study")).toBeInTheDocument();
    expect(within(diagram).getByText("Version 1")).toBeInTheDocument();
    expect(within(diagram).getByText("local.lda_docs")).toBeInTheDocument();
    expect(diagram).toHaveAttribute("data-lifecycle-diagram", "artifact");
  });

  it("maps every requirement to a concrete source and one deployment", () => {
    renderLifecycle("deployment");
    const diagram = screen.getByRole("img", { name: /deployment binding map/i });

    expect(within(diagram).getAllByText("local.lda_docs")).toHaveLength(2);
    expect(within(diagram).getAllByText("local.lda_report")).toHaveLength(2);
    expect(within(diagram).getAllByText("local.issue_board")).toHaveLength(2);
    expect(within(diagram).getByText("lda_report_case_study.default")).toBeInTheDocument();
    expect(within(diagram).getByText("Runnable")).toBeInTheDocument();
    expect(diagram).toHaveAttribute("data-lifecycle-diagram", "deployment");
  });
});
