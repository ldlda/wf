import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { EvidenceRecord } from "../../app/state.js";
import { EvidenceReceipt } from "./EvidenceReceipt.js";

afterEach(() => cleanup());

const record: EvidenceRecord = {
  id: "run-start",
  operation: "workflow.runs.start",
  label: "Start run",
  equivalentCli: "uv run wf run start demo.default",
  request: { deployment_id: "demo.default" },
  response: { result: { status: "interrupted", run_id: "run_demo" } },
  durationMs: 88,
};

describe("EvidenceReceipt", () => {
  it("shows latest operation, status, count, and opens inspection", async () => {
    const user = userEvent.setup();
    const inspect = vi.fn();
    render(<EvidenceReceipt records={[record]} visible onInspect={inspect} />);
    expect(screen.getByText(/workflow\.runs\.start/)).toBeInTheDocument();
    expect(screen.getByText("interrupted")).toBeInTheDocument();
    expect(screen.getByText(/1 record/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /inspect evidence/i }));
    expect(inspect).toHaveBeenCalledOnce();
  });

  it("renders no receipt when the beat keeps evidence hidden", () => {
    render(<EvidenceReceipt records={[record]} visible={false} onInspect={vi.fn()} />);
    expect(screen.queryByRole("button", { name: /inspect evidence/i })).not.toBeInTheDocument();
  });

  it("disables inspection when evidence is unavailable", () => {
    render(<EvidenceReceipt records={[]} visible onInspect={vi.fn()} />);
    expect(screen.getByRole("button", { name: /inspect evidence/i })).toBeDisabled();
  });
});
