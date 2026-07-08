import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import {
  demoBeatLensForBeat,
  type InterruptContractPresentation,
  type OperationPresentation,
} from "./demo-workflow-model.js";
import { DemoOutcomePanel } from "./DemoOutcomePanel.js";

afterEach(() => cleanup());

const operation: OperationPresentation = {
  operation: "workflow.runs.resume",
  status: "completed",
  durationMs: 42,
  command: "uv run wf run resume run_recorded_lda_report",
  deploymentId: "lda_report_workflow.default",
  runId: "run_recorded_lda_report",
  interruptKind: null,
};

const contract: InterruptContractPresentation = {
  kind: "issue_review",
  outcomes: ["submitted", "cancelled"],
  resumeSchema: { type: "object" },
  runId: "run_recorded_lda_report",
};

describe("DemoOutcomePanel", () => {
  it("explains the approval beat as a schema-backed decision", () => {
    render(
      <DemoOutcomePanel
        beatId="approval"
        lens={demoBeatLensForBeat("approval")}
        operation={null}
        contract={contract}
      />,
    );

    expect(screen.getByLabelText("demo outcome proof")).toHaveTextContent("schema-backed");
    expect(screen.getByText("submitted / cancelled")).toBeInTheDocument();
    expect(screen.getByText("run_recorded_lda_report")).toBeInTheDocument();
  });

  it("explains resume as same-run continuation", () => {
    render(
      <DemoOutcomePanel
        beatId="resume"
        lens={demoBeatLensForBeat("resume")}
        operation={operation}
        contract={contract}
      />,
    );

    expect(screen.getByText("Same persisted run")).toBeInTheDocument();
    expect(screen.getByText("workflow.runs.resume")).toBeInTheDocument();
    expect(screen.getByText("completed")).toBeInTheDocument();
  });

  it("explains output and trace without pretending to run live services", () => {
    const { rerender } = render(
      <DemoOutcomePanel
        beatId="output"
        lens={demoBeatLensForBeat("output")}
        operation={null}
        contract={contract}
      />,
    );
    expect(screen.getByText("Report markdown")).toBeInTheDocument();
    expect(screen.getByText("Issue board changes")).toBeInTheDocument();

    rerender(
      <DemoOutcomePanel
        beatId="trace"
        lens={demoBeatLensForBeat("trace")}
        operation={operation}
        contract={contract}
      />,
    );
    expect(screen.getByText("Trace frames")).toBeInTheDocument();
    expect(screen.getByText("Protocol evidence")).toBeInTheDocument();
  });
});
