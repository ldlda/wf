import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WorkflowGraphStage } from "./WorkflowGraphStage.js";
import {
  presentationWorkflowPlan,
  presentationWorkflowNodeIds,
} from "./workflow-graph-data.js";

afterEach(() => cleanup());

const graphNodeByLabel = (label: RegExp): HTMLElement => {
  const nodes = Array.from(document.querySelectorAll<HTMLElement>(".workflow-graph-stage__node"));
  const node = nodes.find((candidate) => label.test(candidate.getAttribute("aria-label") ?? ""));
  if (!node) throw new Error(`Could not find workflow graph node matching ${label}`);
  return node;
};

describe("WorkflowGraphStage", () => {
  it("renders the factual workflow nodes and allows node selection", async () => {
    const selectNode = vi.fn();
    render(
      <WorkflowGraphStage
        execution={{ completedNodeIds: [], currentNodeId: null }}
        selectedNodeId={null}
        selectNode={selectNode}
      />,
    );

    fireEvent.click(graphNodeByLabel(/review issues/i));
    expect(selectNode).toHaveBeenCalledWith("review_issues");
  });

  it("renders the ten-node prepared report workflow plan", () => {
    render(
      <WorkflowGraphStage
        execution={{ completedNodeIds: [], currentNodeId: "read_docs" }}
        selectedNodeId={null}
        selectNode={vi.fn()}
      />,
    );

    const graph = screen.getByRole("group", { name: /workflow graph/i });
    expect(graph).toHaveTextContent("Read documents");
    expect(graph).toHaveTextContent("Reset issue board");
    expect(graph).toHaveTextContent("Analyze");
    expect(graph).toHaveTextContent("Build report");
    expect(graph).toHaveTextContent("Draft issues");
    expect(graph).toHaveTextContent("Review issues");
    expect(graph).toHaveTextContent("Create issues");
    expect(graph).toHaveTextContent("Finalise");
    expect(graph).toHaveTextContent("Revision requested");
    expect(graph).toHaveTextContent("persisted run");
    expect(graph).not.toHaveTextContent("end_cancelled");
    expect(document.querySelectorAll(".workflow-graph-stage__node")).toHaveLength(10);
    expect(presentationWorkflowNodeIds).toEqual([
      "reset_board",
      "read_docs",
      "analyze",
      "build_report",
      "draft_issues",
      "review_issues",
      "create_issues",
      "finalise",
      "revision_requested",
      "end_completed",
    ]);
  });

  it("exposes exactly the ten real workflow nodes as accessible controls", () => {
    render(
      <WorkflowGraphStage
        execution={{ completedNodeIds: [], currentNodeId: null }}
        selectedNodeId={null}
        selectNode={vi.fn()}
      />,
    );

    const graph = screen.getByRole("group", { name: /workflow graph/i });
    // React Flow hides unmeasured node wrappers in jsdom, so assert the
    // rendered button contract directly rather than depending on its role tree.
    const workflowNodes = document.querySelectorAll<HTMLButtonElement>(
      'button[aria-label^="workflow node:"]',
    );
    expect(workflowNodes).toHaveLength(10);
    expect(screen.queryByText(/cancel: no submitted output/i)).not.toBeInTheDocument();
    expect(graph).toHaveTextContent("Revision requested");
  });

  it("does not render graph proof count chips", () => {
    render(
      <WorkflowGraphStage
        execution={{ completedNodeIds: ["read_docs"], currentNodeId: "analyze" }}
        selectedNodeId={null}
        selectNode={vi.fn()}
        proof={{
          runId: "run_recorded_lda_report",
          evidenceLabel: "JSON-RPC evidence",
        }}
      />,
    );

    expect(screen.queryByText("10 plan nodes")).not.toBeInTheDocument();
    expect(screen.queryByText("3 trace frames")).not.toBeInTheDocument();
  });

  it("does not render current-state markers or a state legend", () => {
    render(
      <WorkflowGraphStage
        execution={{
          completedNodeIds: ["read_docs", "reset_board", "analyze", "build_report", "draft_issues"],
          currentNodeId: "review_issues",
        }}
        selectedNodeId={null}
        selectNode={vi.fn()}
      />,
    );

    expect(screen.queryByText("Current")).not.toBeInTheDocument();
    expect(screen.queryByText("Current interrupt")).not.toBeInTheDocument();
    expect(screen.queryByText("Queued")).not.toBeInTheDocument();
    expect(screen.getByLabelText("workflow graph node types")).toHaveTextContent("Action");
    expect(screen.getByLabelText("workflow graph node types")).toHaveTextContent("Human boundary");
    expect(screen.getByLabelText("workflow graph node types")).toHaveTextContent("Outcome");
  });

  it("keeps raw plan facts and canonical labeled edge order", () => {
    expect(presentationWorkflowPlan.edges.map((edge) => `${edge.from}:${edge.outcome}:${edge.to}`)).toEqual([
      "reset_board:ok:read_docs",
      "read_docs:ok:analyze",
      "analyze:ok:build_report",
      "build_report:ok:draft_issues",
      "draft_issues:ok:review_issues",
      "review_issues:submitted:create_issues",
      "create_issues:ok:finalise",
      "finalise:completed:end_completed",
      "review_issues:cancelled:revision_requested",
    ]);
    expect(presentationWorkflowPlan.nodes.every((node) => !("x" in node) && !("y" in node))).toBe(true);
  });

  it("uses a horizontal graph with visible controls", () => {
    render(
      <WorkflowGraphStage
        execution={{ completedNodeIds: ["read_docs"], currentNodeId: "reset_board" }}
        selectedNodeId={null}
        selectNode={vi.fn()}
      />,
    );

    const graph = screen.getByRole("group", { name: "workflow graph" });
    expect(graph).toHaveAttribute("data-graph-direction", "horizontal");
    expect(graph).toHaveAttribute("data-graph-layout", "horizontal");
    expect(graph).toHaveAttribute("data-graph-topology", "prepared-run-branches");
    expect(graph).toHaveAttribute("data-pan-zoom", "enabled");
    expect(graph).toHaveAttribute("data-node-drag", "enabled");
    expect(screen.getByRole("button", { name: /zoom in/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /zoom out/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /fit view/i })).toBeInTheDocument();
  });

  it("separates the submitted and revision branches in two-dimensional space", () => {
    render(
      <WorkflowGraphStage
        execution={{ completedNodeIds: [], currentNodeId: null }}
        selectedNodeId={null}
        selectNode={vi.fn()}
      />,
    );

    const nodePosition = (id: string) => {
      const node = document.querySelector<HTMLElement>(
        `.workflow-graph-stage__node[data-node-id="${id}"]`,
      );
      if (!node) throw new Error(`Missing workflow node ${id}`);
      return { x: Number(node.dataset.positionX), y: Number(node.dataset.positionY) };
    };

    expect(nodePosition("create_issues").y).toBeLessThan(nodePosition("revision_requested").y);
    expect(nodePosition("create_issues").x).toBe(nodePosition("finalise").x);
    expect(nodePosition("finalise").x).toBe(nodePosition("end_completed").x);
    expect(nodePosition("create_issues").y).toBeLessThan(nodePosition("finalise").y);
    expect(nodePosition("finalise").y).toBeLessThan(nodePosition("end_completed").y);
    expect(nodePosition("revision_requested").y).toBeGreaterThan(nodePosition("review_issues").y);
  });

  it("does not invent selected or current node treatment for the static graph", () => {
    render(
      <WorkflowGraphStage
        execution={{ completedNodeIds: ["read_docs"], currentNodeId: "analyze" }}
        selectedNodeId="analyze"
        selectNode={vi.fn()}
      />,
    );

    const nodes = document.querySelectorAll<HTMLButtonElement>(
      'button[aria-label^="workflow node:"]',
    );
    expect(nodes).toHaveLength(10);
    for (const node of nodes) {
      expect(node).not.toHaveAttribute("data-selected");
      expect(node).not.toHaveAttribute("aria-pressed");
      expect(node).not.toHaveAttribute("data-execution-state");
    }
  });

  it("renders the run identity without plan or trace count chips", () => {
    render(
      <WorkflowGraphStage
        execution={{ completedNodeIds: ["read_docs"], currentNodeId: "reset_board" }}
        selectedNodeId={null}
        selectNode={vi.fn()}
        proof={{ runId: "run_recorded_lda_report", evidenceLabel: "JSON-RPC captured" }}
      />,
    );

    expect(screen.getByLabelText("workflow graph proof")).toHaveTextContent("run_recorded_lda_report");
    expect(screen.getByLabelText("workflow graph proof")).toHaveTextContent("JSON-RPC captured");
  });

  it("marks compact graph mode and suppresses proof chips", () => {
    render(
      <WorkflowGraphStage
        execution={{ completedNodeIds: ["read_docs", "reset_board"], currentNodeId: "analyze" }}
        selectedNodeId={null}
        selectNode={vi.fn()}
        variant="compact"
        proof={{ runId: "run_recorded_lda_report", evidenceLabel: "JSON-RPC evidence" }}
      />,
    );

    expect(screen.getByLabelText("workflow graph")).toHaveAttribute("data-graph-variant", "compact");
    expect(screen.queryByLabelText("workflow graph proof")).not.toBeInTheDocument();
  });

  it("keeps full graph mode as the default", () => {
    render(
      <WorkflowGraphStage
        execution={{ completedNodeIds: ["read_docs"], currentNodeId: "reset_board" }}
        selectedNodeId={null}
        selectNode={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("workflow graph")).toHaveAttribute("data-graph-variant", "full");
  });

  it("shows unavailable runId fallback when proof runId is null", () => {
    render(
      <WorkflowGraphStage
        execution={{ completedNodeIds: [], currentNodeId: null }}
        selectedNodeId={null}
        selectNode={vi.fn()}
        proof={{ runId: null, evidenceLabel: "evidence label" }}
      />,
    );

    expect(screen.getByLabelText("workflow graph proof")).toHaveTextContent("run unavailable");
    expect(screen.getByLabelText("workflow graph proof")).toHaveTextContent("evidence label");
  });
});
