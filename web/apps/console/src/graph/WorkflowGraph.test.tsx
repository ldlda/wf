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
        detail: "Start description",
        summary: "2 inputs · 1 state write",
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
  it("renders contract nodes and non-selectable derived connectors horizontally", () => {
    const onNodeSelect = vi.fn();
    const onEdgeSelect = vi.fn();
    const contractModel: WorkflowGraphModel = {
      direction: "LR",
      nodes: [
        {
          id: "contract:input",
          data: {
            nodeId: "contract:input",
            kind: "contract",
            contract: "input",
            label: "Input",
            summary: "2 fields · entry collect",
            nodeRef: null,
            raw: {},
          },
          position: { x: 0, y: 0 },
        },
        {
          id: "collect",
          data: {
            nodeId: "collect",
            kind: "use",
            label: "Collect",
            nodeRef: "demo.collect",
            raw: {},
          },
          position: { x: 250, y: 0 },
        },
      ],
      edges: [{
        id: "contract-edge",
        source: "contract:input",
        target: "collect",
        label: "starts",
        kind: "contract",
      }],
    };
    const { container } = render(
      <WorkflowGraph
        model={contractModel}
        onEdgeSelect={onEdgeSelect}
        onNodeSelect={onNodeSelect}
      />,
    );

    const node = findNodeById(container, "contract:input");
    // React Flow keeps unmeasured test nodes hidden; reveal the wrapper so the
    // accessibility query exercises the same name exposed after browser layout.
    node?.closest<HTMLElement>(".react-flow__node")?.style.setProperty("visibility", "visible");
    expect(screen.getByRole("button", { name: /input workflow contract/i })).toBe(node);
    expect(node).toHaveAttribute("data-contract", "input");
    expect(node?.querySelector(".react-flow__handle-left")).not.toBeNull();
    expect(node?.querySelector(".react-flow__handle-right")).not.toBeNull();
    expect(screen.getByTestId("workflow-graph")).toHaveAttribute(
      "data-derived-connectors",
      "true",
    );
    fireEvent.click(node!);
    fireEvent.keyDown(node!, { key: "Enter" });
    expect(onNodeSelect).toHaveBeenCalledTimes(2);
    expect(onEdgeSelect).not.toHaveBeenCalled();
  });

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

  it("calls onNodeSelect when a focused node is activated by keyboard", () => {
    const onSelect = vi.fn();
    const { container } = render(<WorkflowGraph model={mockModel} onNodeSelect={onSelect} />);
    const reviewNode = findNodeById(container, "review");

    fireEvent.keyDown(reviewNode!, { key: "Enter" });
    fireEvent.keyDown(reviewNode!, { key: " " });

    expect(onSelect).toHaveBeenNthCalledWith(1, "review");
    expect(onSelect).toHaveBeenNthCalledWith(2, "review");
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

  it("renders detail and summary without removing handles", () => {
    const { container } = render(<WorkflowGraph model={mockModel} />);

    expect(screen.getAllByText("Start description").length).toBeGreaterThan(0);
    expect(screen.getAllByText("2 inputs · 1 state write").length).toBeGreaterThan(0);
    expect(container.querySelectorAll(".react-flow__handle")).toHaveLength(6);
  });
});
