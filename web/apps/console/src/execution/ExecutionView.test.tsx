import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { ExecutionView } from "./ExecutionView.js";
import type { TraceFrameView } from "./trace-model.js";

afterEach(() => {
  cleanup();
});

const mockFrames: TraceFrameView[] = [
  {
    nodeId: "start",
    stepType: "use",
    outcome: "ok",
    inputSummary: "{}",
    outputSummary: "{ report_id: string }",
    stateChangeCount: 0,
    raw: {},
  },
  {
    nodeId: "review",
    stepType: "interrupt",
    outcome: "submitted",
    inputSummary: "{ report: string }",
    outputSummary: "{}",
    stateChangeCount: 1,
    raw: {},
  },
];

const mockInterrupt = {
  kind: "human",
  payload: { report: "Please review" },
  outcomes: ["submitted", "rejected"],
  requestSchema: { type: "object", properties: { decision: { type: "string" } } },
  resumeSchema: { type: "object", properties: { decision: { type: "string" } } },
  typed: true,
};

describe("ExecutionView", () => {
  it("renders trace frames", () => {
    render(<ExecutionView frames={mockFrames} />);
    expect(screen.getByText("start")).toBeInTheDocument();
    expect(screen.getByText("review")).toBeInTheDocument();
  });

  it("shows step types", () => {
    render(<ExecutionView frames={mockFrames} />);
    expect(screen.getAllByText("use").length).toBeGreaterThan(0);
    expect(screen.getByText("interrupt")).toBeInTheDocument();
  });

  it("shows outcomes", () => {
    render(<ExecutionView frames={mockFrames} />);
    expect(screen.getAllByText("ok").length).toBeGreaterThan(0);
    expect(screen.getByText("submitted")).toBeInTheDocument();
  });

  it("calls onSelectNode when frame is clicked", () => {
    const onSelect = vi.fn();
    render(<ExecutionView frames={mockFrames} onSelectNode={onSelect} />);
    const reviewNodes = screen.getAllByText("review");
    fireEvent.click(reviewNodes[0]!);
    expect(onSelect).toHaveBeenCalledWith("review");
  });

  it("renders interrupt details", () => {
    render(<ExecutionView frames={mockFrames} interrupt={mockInterrupt} />);
    expect(screen.getByText(/human/i)).toBeInTheDocument();
    expect(screen.getByText(/submitted, rejected/i)).toBeInTheDocument();
  });

  it("shows empty state when no frames", () => {
    render(<ExecutionView frames={[]} />);
    expect(screen.getByText(/no frames/i)).toBeInTheDocument();
  });
});
