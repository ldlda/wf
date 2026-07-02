import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { LdaReportDemoPanel } from "./LdaReportDemoPanel.js";

const baseState = {
  message: null as string | null,
  runId: null as string | null,
  interruptPayload: null as null,
  output: null as null,
  trace: null as null,
};

describe("LdaReportDemoPanel", () => {
  it("shows setup commands when the prepared deployment is missing", () => {
    render(
      <LdaReportDemoPanel
        controller={{
          state: { ...baseState, phase: "missing" },
          refresh: vi.fn(),
          startRun: vi.fn(),
          submitSelectedIssues: vi.fn(),
          cancelReview: vi.fn(),
        }}
      />,
    );

    expect(screen.getByText(/prepared demo deployment is missing/i)).toBeInTheDocument();
    expect(screen.getByText(/wf-rpc-server --config examples\/lda_report_workflow\/wf.config.json/i)).toBeInTheDocument();
  });

  it("starts the demo when ready", async () => {
    const startRun = vi.fn();
    render(
      <LdaReportDemoPanel
        controller={{
          state: { ...baseState, phase: "ready" },
          refresh: vi.fn(),
          startRun,
          submitSelectedIssues: vi.fn(),
          cancelReview: vi.fn(),
        }}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: /start demo run/i }));
    expect(startRun).toHaveBeenCalledOnce();
  });

  it("disables refresh during interrupt to preserve runId", () => {
    const { container } = render(
      <LdaReportDemoPanel
        controller={{
          state: {
            ...baseState,
            phase: "interrupted",
            runId: "run_demo",
            interruptPayload: {
              report_markdown: "# Report",
              proposed_issues: [],
            },
          },
          refresh: vi.fn(),
          startRun: vi.fn(),
          submitSelectedIssues: vi.fn(),
          cancelReview: vi.fn(),
        }}
      />,
    );

    const buttons = container.querySelectorAll("button");
    const refreshButton = Array.from(buttons).find(
      (b) => b.textContent?.includes("Refresh demo state"),
    );
    expect(refreshButton).toBeDefined();
    expect(refreshButton).toBeDisabled();
  });

  it("allows refresh after completion so the demo can run again", () => {
    const view = render(
      <LdaReportDemoPanel
        controller={{
          state: {
            ...baseState,
            phase: "completed",
            output: {
              approved: true,
              markdown: "# Report",
              created_issues: [],
              selected_issue_ids: [],
              comment: null,
            },
          },
          refresh: vi.fn(),
          startRun: vi.fn(),
          submitSelectedIssues: vi.fn(),
          cancelReview: vi.fn(),
        }}
      />,
    );

    expect(
      within(view.container).getByRole("button", { name: /refresh demo state/i }),
    ).toBeEnabled();
  });

  it("displays trace frames in completed view", () => {
    render(
      <LdaReportDemoPanel
        controller={{
          state: {
            ...baseState,
            phase: "completed",
            output: {
              approved: true,
              markdown: "# Report",
              created_issues: [{ id: "ISSUE-001", title: "Demo", url: "local://issues/ISSUE-001" }],
              selected_issue_ids: ["demo-issue-1"],
              comment: "Create it.",
            },
            trace: {
              frames: [
                { nodeId: "generate", stepType: "tool", outcome: "completed", resolvedInput: {}, output: {}, stateChanges: {} },
                { nodeId: "review", stepType: "interrupt", outcome: "submitted", resolvedInput: {}, output: {}, stateChanges: {} },
              ],
              traceStart: 0,
              traceLimit: 50,
              traceTruncated: false,
            },
          },
          refresh: vi.fn(),
          startRun: vi.fn(),
          submitSelectedIssues: vi.fn(),
          cancelReview: vi.fn(),
        }}
      />,
    );

    expect(screen.getByText("Execution trace (2 frames)")).toBeInTheDocument();
    expect(screen.getByText("generate")).toBeInTheDocument();
    expect(screen.getByText("review")).toBeInTheDocument();
  });
});
