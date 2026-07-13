import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { DemoEvent } from "../demo/timeline/models.js";
import { OperationBlock } from "./OperationBlock.js";

afterEach(() => cleanup());

const event: DemoEvent = {
  id: "recorded-1-run-start",
  sequence: 1,
  stage: "run_start",
  operation: "workflow.runs.start",
  reason: "Start the prepared report workflow.",
  equivalentCli: "uv run wf run start lda_report_case_study.default --input '<json>'",
  params: { deployment_id: "lda_report_case_study.default" },
  rawResponse: { result: { status: "interrupted" } },
  interpreted: {
    status: "interrupted",
    interrupt: { kind: "issue_review" },
  },
  durationMs: 88,
  resultingIds: {
    deploymentId: "lda_report_case_study.default",
    runId: "run_demo",
  },
  recordedAt: "2026-07-03T00:00:01.000Z",
};

describe("OperationBlock", () => {
  it("shows command, interpreted summary, and protocol receipt action in expanded mode", () => {
    render(<OperationBlock event={event} variant="expanded" openEvidence={vi.fn()} />);

    expect(screen.getByText(/workflow.runs.start/i)).toBeInTheDocument();
    expect(screen.getByText(/uv run wf run start/i)).toBeInTheDocument();
    expect(screen.getByText("Workflow operation")).toBeInTheDocument();
    expect(screen.getAllByText(/interrupted/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/issue_review/i)).toBeInTheDocument();
    expect(screen.getAllByText(/run_demo/i).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /inspect protocol receipt/i })).toBeInTheDocument();
    expect(screen.queryByText(/view raw evidence/i)).not.toBeInTheDocument();
  });

  it("shows compact receipt with operation, status, duration, and run id", () => {
    render(<OperationBlock event={event} variant="receipt" openEvidence={vi.fn()} />);

    expect(screen.getByText(/workflow.runs.start/i)).toBeInTheDocument();
    expect(screen.getByText(/interrupted/i)).toBeInTheDocument();
    expect(screen.getByText(/88 ms/i)).toBeInTheDocument();
    expect(screen.getByText(/run_demo/i)).toBeInTheDocument();
    expect(screen.queryByText("Workflow operation")).not.toBeInTheDocument();
  });

  it("invokes onOpenEvidence when the evidence action is clicked", async () => {
    const openEvidence = vi.fn();
    render(<OperationBlock event={event} variant="expanded" openEvidence={openEvidence} />);

    await userEvent.click(screen.getByRole("button", { name: /inspect protocol receipt/i }));
    expect(openEvidence).toHaveBeenCalledOnce();
  });

  it("renders deployment and run ids as unavailable when missing", () => {
    const eventWithoutIds: DemoEvent = {
      ...event,
      resultingIds: { deploymentId: null, runId: null },
    };
    render(<OperationBlock event={eventWithoutIds} variant="expanded" openEvidence={vi.fn()} />);

    expect(screen.getAllByText(/unavailable/i).length).toBeGreaterThan(0);
  });
});
