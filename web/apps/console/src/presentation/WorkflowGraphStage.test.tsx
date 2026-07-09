import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WorkflowGraphStage } from "./WorkflowGraphStage.js";
import { presentationEdges, presentationNodes } from "./workflow-graph-data.js";

afterEach(() => cleanup());

const graphNodeByLabel = (label: RegExp): HTMLElement => {
  const nodes = Array.from(document.querySelectorAll<HTMLElement>(".workflow-graph-stage__node"));
  const node = nodes.find((candidate) => label.test(candidate.getAttribute("aria-label") ?? ""));
  if (!node) throw new Error(`Could not find workflow graph node matching ${label}`);
  return node;
};

describe("WorkflowGraphStage", () => {
  it("renders curated workflow nodes and allows node selection", async () => {
    const selectNode = vi.fn();
    render(
      <WorkflowGraphStage
        execution={{ completedNodeIds: [], currentNodeId: null }}
        selectedNodeId={null}
        selectNode={selectNode}
      />,
    );

    fireEvent.click(graphNodeByLabel(/issue review/i));
    expect(selectNode).toHaveBeenCalledWith("review_issues");
  });

  it("renders the prepared report workflow plan nodes", () => {
    render(
      <WorkflowGraphStage
        execution={{ completedNodeIds: [], currentNodeId: "read_docs" }}
        selectedNodeId={null}
        selectNode={vi.fn()}
      />,
    );

    const graph = screen.getByRole("group", { name: /workflow graph/i });
    expect(graph).toHaveTextContent("Read docs");
    expect(graph).toHaveTextContent("Reset board");
    expect(graph).toHaveTextContent("Analyze");
    expect(graph).toHaveTextContent("Build report");
    expect(graph).toHaveTextContent("Draft issues");
    expect(graph).toHaveTextContent("Issue review");
    expect(graph).toHaveTextContent("Create issues");
    expect(graph).toHaveTextContent("Finalise");
    expect(graph).toHaveTextContent("Revision requested");
    expect(graph).toHaveTextContent("Completed");
    expect(graph).not.toHaveTextContent("Cancelled");
    expect(document.querySelectorAll(".workflow-graph-stage__node")).toHaveLength(10);
  });

  it("labels graph proof as plan nodes and trace frames separately", () => {
    render(
      <WorkflowGraphStage
        execution={{ completedNodeIds: ["read_docs"], currentNodeId: "analyze" }}
        selectedNodeId={null}
        selectNode={vi.fn()}
        proof={{
          runId: "run_recorded_lda_report",
          planLabel: "10 plan nodes",
          traceLabel: "3 trace frames",
          evidenceLabel: "JSON-RPC evidence",
        }}
      />,
    );

    const proof = screen.getByLabelText("workflow graph proof");
    expect(proof).toHaveTextContent("10 plan nodes");
    expect(proof).toHaveTextContent("3 trace frames");
  });

  it("distinguishes completed, current interrupt, and future nodes semantically", () => {
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

    const readDocs = graphNodeByLabel(/read docs/i);
    const reviewIssues = graphNodeByLabel(/issue review/i);
    const revisionReq = graphNodeByLabel(/revision requested/i);

    expect(readDocs).toHaveAttribute("data-execution-state", "completed");
    expect(reviewIssues).toHaveAttribute("data-execution-state", "current");
    expect(reviewIssues).toHaveAttribute("data-current-interrupt", "true");
    expect(reviewIssues).toHaveTextContent("Current interrupt");
    expect(revisionReq).toHaveAttribute("data-execution-state", "future");
  });

  it("renders connectors between nodes", () => {
    expect(presentationEdges).toHaveLength(9);
    expect(presentationEdges).toContainEqual({
      from: "read_docs",
      to: "reset_board",
      fromHandle: "right",
      toHandle: "left",
    });
    expect(presentationEdges).toContainEqual({
      from: "review_issues",
      to: "revision_requested",
      fromHandle: "bottom",
      toHandle: "top",
    });
  });

  it("uses flow coordinates rather than viewport percentages", () => {
    render(
      <WorkflowGraphStage
        execution={{ completedNodeIds: ["read_docs"], currentNodeId: "reset_board" }}
        selectedNodeId={null}
        selectNode={vi.fn()}
      />,
    );

    for (const node of presentationNodes) {
      expect(Number.isFinite(node.x)).toBe(true);
      expect(Number.isFinite(node.y)).toBe(true);
    }
  });

  it("renders compact run proof inside the graph", () => {
    render(
      <WorkflowGraphStage
        execution={{ completedNodeIds: ["read_docs"], currentNodeId: "reset_board" }}
        selectedNodeId={null}
        selectNode={vi.fn()}
        proof={{ runId: "run_recorded_lda_report", planLabel: "10 plan nodes", traceLabel: "3 trace frames", evidenceLabel: "JSON-RPC captured" }}
      />,
    );

    expect(screen.getByLabelText("workflow graph proof")).toHaveTextContent("run_recorded_lda_report");
    expect(screen.getByLabelText("workflow graph proof")).toHaveTextContent("10 plan nodes");
    expect(screen.getByLabelText("workflow graph proof")).toHaveTextContent("3 trace frames");
    expect(screen.getByLabelText("workflow graph proof")).toHaveTextContent("JSON-RPC captured");
  });

  it("marks compact graph mode and suppresses proof chips", () => {
    render(
      <WorkflowGraphStage
        execution={{ completedNodeIds: ["read_docs", "reset_board"], currentNodeId: "analyze" }}
        selectedNodeId={null}
        selectNode={vi.fn()}
        variant="compact"
        proof={{ runId: "run_recorded_lda_report", planLabel: "10 plan nodes", traceLabel: "3 trace frames", evidenceLabel: "JSON-RPC evidence" }}
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
        proof={{ runId: null, planLabel: "10 plan nodes", traceLabel: "trace label", evidenceLabel: "evidence label" }}
      />,
    );

    expect(screen.getByLabelText("workflow graph proof")).toHaveTextContent("run unavailable");
    expect(screen.getByLabelText("workflow graph proof")).toHaveTextContent("trace label");
    expect(screen.getByLabelText("workflow graph proof")).toHaveTextContent("evidence label");
  });
});
