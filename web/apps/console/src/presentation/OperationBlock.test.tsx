import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
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
  it("shows command, raw response, and interpreted result", () => {
    render(<OperationBlock event={event} />);

    expect(screen.getByText(/workflow.runs.start/i)).toBeInTheDocument();
    expect(screen.getByText(/uv run wf run start/i)).toBeInTheDocument();
    expect(screen.getByText("Raw")).toBeInTheDocument();
    expect(screen.getByText("Interpreted")).toBeInTheDocument();
    expect(screen.getByText(/run_demo/i)).toBeInTheDocument();
  });
});
