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

    expect(screen.getByRole("group", { name: "workflow graph" })).toHaveAttribute("data-graph-direction", "horizontal");
    expect(screen.getByRole("button", { name: /zoom in/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /zoom out/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /fit view/i })).toBeInTheDocument();
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
