import { describe, it, expect, vi, beforeAll, afterAll } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { WorkflowGraph } from "./WorkflowGraph.js";
import type { WorkflowGraphModel } from "./graph-model.js";

class MockResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

beforeAll(() => {
  globalThis.ResizeObserver = MockResizeObserver as unknown as typeof ResizeObserver;
  globalThis.DOMRect = {
    fromRect: () => ({
      x: 0,
      y: 0,
      width: 0,
      height: 0,
      top: 0,
      right: 0,
      bottom: 0,
      left: 0,
      toJSON() {},
    }),
  } as unknown as typeof DOMRect;
});

afterAll(() => {
  delete (globalThis as Record<string, unknown>).ResizeObserver;
  delete (globalThis as Record<string, unknown>).DOMRect;
});

const mockModel: WorkflowGraphModel = {
  nodes: [
    {
      id: "start",
      data: {
        nodeId: "start",
        kind: "use",
        label: "Start",
        nodeRef: "workflow.start",
        raw: {},
      },
      position: { x: 0, y: 0 },
    },
    {
      id: "review",
      data: {
        nodeId: "review",
        kind: "interrupt",
        label: "Review",
        nodeRef: null,
        raw: {},
      },
      position: { x: 200, y: 0 },
    },
    {
      id: "end",
      data: {
        nodeId: "end",
        kind: "end",
        label: "End",
        nodeRef: null,
        raw: {},
      },
      position: { x: 400, y: 0 },
    },
  ],
  edges: [
    { id: "e1", source: "start", target: "review", label: "ok" },
    { id: "e2", source: "review", target: "end", label: "submitted" },
  ],
};

const findNodeById = (container: HTMLElement, nodeId: string): HTMLElement | null =>
  container.querySelector(`[data-node-id="${nodeId}"]`);

describe("WorkflowGraph", () => {
  it("renders nodes and edges", () => {
    const { container } = render(<WorkflowGraph model={mockModel} />);
    expect(screen.getByText("Start")).toBeInTheDocument();
    expect(screen.getByText("Review")).toBeInTheDocument();
    expect(screen.getByText("End")).toBeInTheDocument();
    expect(findNodeById(container, "start")).not.toBeNull();
    expect(findNodeById(container, "review")).not.toBeNull();
    expect(findNodeById(container, "end")).not.toBeNull();
    expect(container.querySelectorAll(".react-flow__handle")).toHaveLength(6);
  });

  it("calls onNodeSelect when node is clicked", () => {
    const onSelect = vi.fn();
    const { container } = render(<WorkflowGraph model={mockModel} onNodeSelect={onSelect} />);
    const reviewNode = findNodeById(container, "review");
    fireEvent.click(reviewNode!);
    expect(onSelect).toHaveBeenCalledWith("review");
  });

  it("highlights active node when activeNodeId is provided", () => {
    const { container } = render(<WorkflowGraph model={mockModel} activeNodeId="review" />);
    const reviewNode = findNodeById(container, "review");
    expect(reviewNode).toHaveAttribute("data-active", "true");
  });

  it("does not highlight nodes when activeNodeId is null", () => {
    const { container } = render(<WorkflowGraph model={mockModel} activeNodeId={null} />);
    const reviewNode = findNodeById(container, "review");
    expect(reviewNode).toHaveAttribute("data-active", "false");
  });

  it("shows empty state when no nodes", () => {
    const emptyModel: WorkflowGraphModel = { nodes: [], edges: [] };
    render(<WorkflowGraph model={emptyModel} />);
    expect(screen.getByText(/no nodes/i)).toBeInTheDocument();
  });
});
