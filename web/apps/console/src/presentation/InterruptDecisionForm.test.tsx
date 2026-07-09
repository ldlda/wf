import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { RunFactsInterrupt } from "./demo-run-facts.js";
import { InterruptDecisionForm } from "./InterruptDecisionForm.js";

const interrupt: RunFactsInterrupt = {
  kind: "issue_review",
  typed: true,
  outcomes: ["submitted", "cancelled"],
  proposedIssues: [
    {
      id: "risk-1",
      title: "Prepare the defense walkthrough",
      body: "Review the live and replay paths before the defense.",
      severity: "medium",
    },
    {
      id: "risk-2",
      title: "Update the architecture diagram",
      body: "Ensure the diagram reflects the latest changes.",
      severity: "low",
    },
  ],
  reportMarkdownPreview: "# Report\n\nThe workflow substrate is ready.",
};

describe("InterruptDecisionForm", () => {
  afterEach(() => cleanup());

  it("renders proposed issues as checkbox rows with default selection", () => {
    render(
      <InterruptDecisionForm
        interrupt={interrupt}
        runId="run_recorded_lda_report"
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes).toHaveLength(2);
    expect(checkboxes[0]).toBeChecked();
    expect(checkboxes[1]).toBeChecked();
    expect(screen.getByText("Prepare the defense walkthrough")).toBeDefined();
    expect(screen.getByText("Update the architecture diagram")).toBeDefined();
  });

  it("defaults comment field to Create the selected issue.", () => {
    render(
      <InterruptDecisionForm
        interrupt={interrupt}
        runId="run_recorded_lda_report"
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    const textarea = screen.getByRole("textbox", { name: /resume comment/i });
    expect((textarea as HTMLTextAreaElement).value).toBe("Create the selected issue.");
  });

  it("submits selected issue IDs and edited comment", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();

    render(
      <InterruptDecisionForm
        interrupt={interrupt}
        runId="run_recorded_lda_report"
        onSubmit={onSubmit}
        onCancel={vi.fn()}
      />,
    );

    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes.length).toBeGreaterThanOrEqual(2);
    await user.click(checkboxes[1]!);
    expect(checkboxes[0]).toBeChecked();
    expect(checkboxes[1]).not.toBeChecked();

    const textarea = screen.getByRole("textbox", { name: /resume comment/i });
    await user.clear(textarea);
    await user.type(textarea, "Custom comment");

    await user.click(screen.getByRole("button", { name: /submit/i }));

    expect(onSubmit).toHaveBeenCalledWith(
      ["risk-1"],
      "Custom comment",
    );
  });

  it("calls cancel callback without submit", async () => {
    const onCancel = vi.fn();
    const onSubmit = vi.fn();
    const user = userEvent.setup();

    render(
      <InterruptDecisionForm
        interrupt={interrupt}
        runId="run_recorded_lda_report"
        onSubmit={onSubmit}
        onCancel={onCancel}
      />,
    );

    await user.click(screen.getByRole("button", { name: /cancel/i }));

    expect(onCancel).toHaveBeenCalledOnce();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("shows terminal outcome label when state is submitted", () => {
    render(
      <InterruptDecisionForm
        interrupt={interrupt}
        runId="run_recorded_lda_report"
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
        terminalOutcome="submitted"
      />,
    );

    expect(screen.getByText(/submitted/i)).toBeDefined();
    expect(screen.queryByRole("button", { name: /submit/i })).toBeFalsy();
    expect(screen.queryByRole("button", { name: /cancel/i })).toBeFalsy();
  });

  it("shows terminal outcome label when state is cancelled", () => {
    render(
      <InterruptDecisionForm
        interrupt={interrupt}
        runId="run_recorded_lda_report"
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
        terminalOutcome="cancelled"
      />,
    );

    expect(screen.getByText(/cancelled/i)).toBeDefined();
    expect(screen.queryByRole("button", { name: /submit/i })).toBeFalsy();
    expect(screen.queryByRole("button", { name: /cancel/i })).toBeFalsy();
  });
});
