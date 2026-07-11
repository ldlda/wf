import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SchemaApprovalSurface } from "./SchemaApprovalSurface.js";

afterEach(() => cleanup());

describe("SchemaApprovalSurface", () => {
  it("renders explicit schema fields and outcome actions", () => {
    const onSubmit = vi.fn();
    const onRequestRevision = vi.fn();

    render(
      <SchemaApprovalSurface
        title="Issue review resume"
        schema={{
          type: "object",
          required: ["selected_issue_ids"],
          properties: {
            selected_issue_ids: { type: "array", description: "Issue ids to create" },
            comment: { type: "string" },
          },
        }}
        payload={{ selected_issue_ids: ["risk-1"], comment: "Create the selected issue." }}
        outcomes={["submitted", "cancelled"]}
        runId="run_recorded_lda_report"
        onSubmit={onSubmit}
        onRequestRevision={onRequestRevision}
      />,
    );

    const surface = screen.getByRole("group", { name: /issue review resume/i });
    expect(within(surface).getByText("selected issue ids")).toBeInTheDocument();
    expect(within(surface).getByText("required")).toBeInTheDocument();
    expect(within(surface).getByText("[\"risk-1\"]")).toBeInTheDocument();
    expect(within(surface).getByText("run_recorded_lda_report")).toBeInTheDocument();

    fireEvent.click(within(surface).getByRole("button", { name: /submit/i }));
    fireEvent.click(within(surface).getByRole("button", { name: /request revision/i }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onRequestRevision).toHaveBeenCalledTimes(1);
  });

  it("renders payload preview for loose object schemas", () => {
    render(
      <SchemaApprovalSurface
        title="Issue review resume"
        schema={{ type: "object" }}
        payload={{ selected_issue_ids: ["risk-1"], comment: "Create the selected issue." }}
        outcomes={["submitted", "cancelled"]}
        runId="run_recorded_lda_report"
      />,
    );

    expect(screen.getByText("Recorded resume payload for this decision.")).toBeInTheDocument();
    expect(screen.getByText("selected_issue_ids")).toBeInTheDocument();
    expect(screen.getByText("[\"risk-1\"]")).toBeInTheDocument();
  });

  it("shows submitted and revision-requested states without active actions", () => {
    const { rerender } = render(
      <SchemaApprovalSurface
        title="Issue review resume"
        schema={{ type: "object" }}
        payload={{}}
        outcomes={["submitted", "cancelled"]}
        runId={null}
        state="submitted"
      />,
    );

    expect(screen.getByText("Outcome: submitted")).toBeInTheDocument();

    rerender(
      <SchemaApprovalSurface
        title="Issue review resume"
        schema={{ type: "object" }}
        payload={{}}
        outcomes={["submitted", "cancelled"]}
        runId={null}
        state="revision_requested"
      />,
    );

    expect(screen.getByText("Outcome: revision requested")).toBeInTheDocument();
  });
});
