import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { EvidenceRecord } from "../app/state.js";
import { EvidenceDrawer } from "./EvidenceDrawer.js";

afterEach(() => cleanup());

const record: EvidenceRecord = {
  id: "demo-run-start",
  operation: "workflow.runs.start",
  label: "Start run",
  equivalentCli: "uv run wf run start lda_report_case_study.default",
  request: { deployment_id: "lda_report_case_study.default" },
  response: { result: { status: "interrupted" } },
  durationMs: 88,
};

describe("EvidenceDrawer", () => {
  it("renders current evidence records and can close", () => {
    const close = vi.fn();
    render(<EvidenceDrawer records={[record]} mode="open" close={close} />);

    expect(screen.getByRole("complementary", { name: /presentation evidence/i })).toBeInTheDocument();
    expect(screen.getByText(/workflow.runs.start/i)).toBeInTheDocument();
    expect(screen.getByText(/interrupted/i)).toBeInTheDocument();
  });
});
