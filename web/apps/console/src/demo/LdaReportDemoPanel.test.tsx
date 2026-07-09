import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, it, expect, vi } from "vitest";
import { LdaReportDemoPanel } from "./LdaReportDemoPanel.js";

afterEach(() => cleanup());

const baseController = {
  state: {
    mode: "live" as const,
    phase: "ready" as const,
    events: [],
    appliedCount: 0,
    autoplay: false,
    error: null,
  },
  inFlight: false,
  interruptPayload: null,
  output: null,
  trace: null,
  missingDeploymentMessage: null,
  recordingId: null,
  canStart: true,
  setMode: vi.fn(),
  start: vi.fn(),
  pause: vi.fn(),
  play: vi.fn(),
  next: vi.fn(),
  submitSelectedIssues: vi.fn(),
  cancelReview: vi.fn(),
  restart: vi.fn(),
  primeReplayToStage: vi.fn(),
};

describe("LdaReportDemoPanel", () => {
  it("shows setup commands when live mode has no connection", () => {
    render(
      <LdaReportDemoPanel
        controller={{
          ...baseController,
          missingDeploymentMessage: "Not connected. Select Live and connect to a workflow server, or switch to Replay.",
        }}
      />,
    );

    expect(screen.getByText(/prepared demo deployment is missing/i)).toBeInTheDocument();
    expect(screen.getByText(/wf-rpc-server --config examples\/lda_report_workflow\/wf.config.json/i)).toBeInTheDocument();
  });

  it("starts a connected live demo when Start presentation is clicked", async () => {
    const start = vi.fn();
    render(
      <LdaReportDemoPanel
        controller={{ ...baseController, start, canStart: true }}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: /start presentation/i }));
    expect(start).toHaveBeenCalledOnce();
  });

  it("disables live start without a connection but allows offline replay", () => {
    const { rerender } = render(
      <LdaReportDemoPanel
        controller={{
          ...baseController,
          canStart: false,
          missingDeploymentMessage: "Not connected.",
        }}
      />,
    );
    expect(screen.getByRole("button", { name: /start presentation/i })).toBeDisabled();

    rerender(
      <LdaReportDemoPanel
        controller={{
          ...baseController,
          canStart: true,
          state: { ...baseController.state, mode: "replay" },
          recordingId: "lda-report-success-v1",
        }}
      />,
    );
    expect(screen.getByRole("button", { name: /start presentation/i })).toBeEnabled();
  });

  it("shows replay attribution when in replay mode", () => {
    render(
      <LdaReportDemoPanel
        controller={{
          ...baseController,
          state: { ...baseController.state, mode: "replay" },
          recordingId: "lda-report-success-v1",
        }}
      />,
    );

    expect(screen.getByText(/recorded replay/i)).toBeInTheDocument();
    expect(screen.getByText(/lda-report-success-v1/)).toBeInTheDocument();
  });

  it("displays trace frames in completed view", () => {
    render(
      <LdaReportDemoPanel
        controller={{
          ...baseController,
          state: {
            ...baseController.state,
            phase: "completed",
          },
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
        }}
      />,
    );

    expect(screen.getByText("Execution trace (2 frames)")).toBeInTheDocument();
    expect(screen.getByText("generate")).toBeInTheDocument();
    expect(screen.getByText("review")).toBeInTheDocument();
  });

  it("shows Continue button in replay review mode", () => {
    render(
      <LdaReportDemoPanel
        controller={{
          ...baseController,
          state: { ...baseController.state, mode: "replay", phase: "review" },
          interruptPayload: {
            report_markdown: "# Report",
            proposed_issues: [{ id: "risk-1", title: "Defense", body: "Review paths.", severity: "medium" }],
          },
          recordingId: "lda-report-success-v1",
        }}
      />,
    );

    expect(screen.getByRole("button", { name: /continue/i })).toBeInTheDocument();
    expect(screen.getByText(/replay does not create real issues/i)).toBeInTheDocument();
  });
});
