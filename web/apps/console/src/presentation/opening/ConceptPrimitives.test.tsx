import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ConceptIcon, ConceptNode, ConceptRail } from "./ConceptPrimitives.js";

describe("ConceptPrimitives", () => {
  it("renders labelled concept icons without external icon dependencies", () => {
    render(<ConceptIcon name="planner" label="Planner icon" />);

    expect(screen.getByRole("img", { name: "Planner icon" })).toBeInTheDocument();
  });

  it("renders concept nodes with stable emphasis attributes", () => {
    render(
      <ConceptNode title="Workflow Platform" subtitle="submitted substrate" icon="platform" emphasis="primary">
        <span>Typed · Durable · Inspectable</span>
      </ConceptNode>,
    );

    const node = screen.getByRole("group", { name: /Workflow Platform/i });
    expect(node).toHaveAttribute("data-concept-emphasis", "primary");
    expect(node).toHaveTextContent("submitted substrate");
    expect(node).toHaveTextContent("Typed · Durable · Inspectable");
  });

  it("renders a labelled concept rail", () => {
    render(
      <ConceptRail label="Reusable automation rail">
        <ConceptNode title="Design" icon="design" />
        <ConceptNode title="Run" icon="run" />
      </ConceptRail>,
    );

    expect(screen.getByRole("group", { name: "Reusable automation rail" })).toBeInTheDocument();
    expect(screen.getByText("Design")).toBeInTheDocument();
    expect(screen.getByText("Run")).toBeInTheDocument();
  });
});
