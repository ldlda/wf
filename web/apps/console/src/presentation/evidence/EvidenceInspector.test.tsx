import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { EvidenceRecord } from "../../app/state.js";
import { EvidenceInspector } from "./EvidenceInspector.js";

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

const traceRecord: EvidenceRecord = {
  ...record,
  id: "run-trace",
  operation: "workflow.runs.trace",
  label: "Inspect trace",
  equivalentCli: "uv run wf run trace run_demo",
  response: { result: { status: "completed", frames: [] } },
  durationMs: 34,
};

describe("EvidenceInspector", () => {
  it("opens on interpreted evidence and switches to raw request and response", async () => {
    const user = userEvent.setup();
    render(<EvidenceInspector records={[record]} open onClose={vi.fn()} />);
    expect(screen.getByRole("dialog", { name: /evidence inspector/i })).toBeInTheDocument();
    expect(screen.getAllByText("workflow.runs.start").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("88 ms")).toBeInTheDocument();
    expect(screen.getByText("demo.default")).toBeInTheDocument();
    expect(screen.getByText("run_demo")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: /raw/i }));
    expect(screen.getByText(/uv run wf run start/i)).toBeInTheDocument();
    expect(screen.getByText(/deployment_id/i)).toBeInTheDocument();
    expect(screen.getByText(/interrupted/i)).toBeInTheDocument();
  });

  it("keeps the selected record while changing views", async () => {
    const user = userEvent.setup();
    render(<EvidenceInspector records={[record, traceRecord]} open onClose={vi.fn()} />);
    await user.selectOptions(screen.getByLabelText(/evidence record/i), record.id);
    await user.click(screen.getByRole("tab", { name: /raw/i }));
    expect(screen.getByLabelText(/evidence record/i)).toHaveValue(record.id);
  });

  it("focuses close on open and restores the previous trigger on unmount", () => {
    const trigger = document.createElement("button");
    document.body.append(trigger);
    trigger.focus();
    const view = render(<EvidenceInspector records={[record]} open onClose={vi.fn()} />);
    expect(screen.getByRole("button", { name: /close evidence/i })).toHaveFocus();
    view.unmount();
    expect(trigger).toHaveFocus();
    trigger.remove();
  });

  it("wraps keyboard focus inside the inspector", async () => {
    const user = userEvent.setup();
    render(<EvidenceInspector records={[record]} open onClose={vi.fn()} />);
    const close = screen.getByRole("button", { name: /close evidence/i });
    const raw = screen.getByRole("tab", { name: /raw/i });
    close.focus();
    await user.tab({ shift: true });
    expect(raw).toHaveFocus();
    await user.tab();
    expect(close).toHaveFocus();
  });

  it("renders a bounded unavailable state with no records", () => {
    render(<EvidenceInspector records={[]} open onClose={vi.fn()} />);
    expect(screen.getByText(/evidence unavailable/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/evidence record/i)).not.toBeInTheDocument();
  });

  it("shows a formatting note for non-serializable raw evidence", async () => {
    const user = userEvent.setup();
    const cyclic: Record<string, unknown> = {};
    cyclic.self = cyclic;
    render(<EvidenceInspector records={[{ ...record, response: cyclic }]} open onClose={vi.fn()} />);
    await user.click(screen.getByRole("tab", { name: /raw/i }));
    expect(screen.getByText(/could not format as json/i)).toBeInTheDocument();
  });
});
