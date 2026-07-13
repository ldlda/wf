import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { projectPreparedLifecycleStep } from "./authoring-projection.js";
import { AuthoringWorkflowDiagram } from "./AuthoringWorkflowDiagram.js";

afterEach(cleanup);

const renderDiagram = (step: "draft" | "diagnose" | "repair") => {
  const projection = projectPreparedLifecycleStep(step);
  if (
    projection.evidence.kind !== "draft"
    && projection.evidence.kind !== "diagnostic"
    && projection.evidence.kind !== "repair"
  ) {
    throw new Error(`unexpected evidence for ${step}`);
  }
  return render(
    <AuthoringWorkflowDiagram mode={step === "diagnose" ? "diagnostic" : step} evidence={projection.evidence} />,
  );
};

describe("AuthoringWorkflowDiagram", () => {
  it.each(["draft", "diagnose", "repair"] as const)(
    "preserves workflow node identity in %s mode",
    (step) => {
      renderDiagram(step);
      const diagram = screen.getByRole("img", { name: /authoring workflow diagram/i });

      expect(within(diagram).getByText("read_documents")).toBeInTheDocument();
      expect(within(diagram).getByText("analyze")).toBeInTheDocument();
      expect(within(diagram).getByText("END")).toBeInTheDocument();
      expect(diagram.querySelectorAll("[data-authoring-node-id]")).toHaveLength(3);
    },
  );

  it("shows an absent analyze.ok route as the diagnostic headline", () => {
    renderDiagram("diagnose");

    expect(screen.getByRole("img", { name: /analyze ok route is missing/i })).toBeInTheDocument();
  });

  it("restores analyze.ok without retaining the missing-route marker", () => {
    renderDiagram("repair");

    expect(screen.getByRole("img", { name: /analyze ok route restored/i })).toBeInTheDocument();
    expect(screen.queryByText("Missing route")).not.toBeInTheDocument();
  });

  it("reserves a wider rank for the route-state edge label", () => {
    renderDiagram("repair");
    const analyze = document.querySelector('[data-id="analyze"]');
    const end = document.querySelector('[data-id="__end__"]');

    expect(analyze).toHaveStyle({ width: "224px" });
    expect(end).toHaveStyle({ width: "224px" });
    expect(analyze?.getAttribute("style")).not.toEqual(end?.getAttribute("style"));
  });
});
