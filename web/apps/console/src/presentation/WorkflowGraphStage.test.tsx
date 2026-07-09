import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { presentationNodes, WorkflowGraphStage } from "./WorkflowGraphStage.js";

afterEach(() => cleanup());

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

    await userEvent.click(screen.getByRole("button", { name: /issue review/i }));
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
    expect(graph).toHaveTextContent("Cancelled");
    expect(screen.getAllByRole("button", { name: /queued|current|completed|interrupt/i })).toHaveLength(11);
  });

  it("labels graph proof as plan nodes and trace frames separately", () => {
    render(
      <WorkflowGraphStage
        execution={{ completedNodeIds: ["read_docs"], currentNodeId: "analyze" }}
        selectedNodeId={null}
        selectNode={vi.fn()}
        proof={{
          runId: "run_recorded_lda_report",
          planLabel: "11 plan nodes",
          traceLabel: "3 trace frames",
          evidenceLabel: "JSON-RPC evidence",
        }}
      />,
    );

    const proof = screen.getByLabelText("workflow graph proof");
    expect(proof).toHaveTextContent("11 plan nodes");
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

    const readDocs = screen.getByRole("button", { name: /read docs/i });
    const reviewIssues = screen.getByRole("button", { name: /issue review/i });
    const revisionReq = screen.getByRole("button", { name: /revision requested/i });

    expect(readDocs).toHaveAttribute("data-execution-state", "completed");
    expect(reviewIssues).toHaveAttribute("data-execution-state", "current");
    expect(reviewIssues).toHaveAttribute("data-current-interrupt", "true");
    expect(reviewIssues).toHaveTextContent("Current interrupt");
    expect(revisionReq).toHaveAttribute("data-execution-state", "future");
  });

  it("renders connectors between nodes", () => {
    render(
      <WorkflowGraphStage
        execution={{ completedNodeIds: ["read_docs"], currentNodeId: "reset_board" }}
        selectedNodeId={null}
        selectNode={vi.fn()}
      />,
    );

    const connectors = screen.getAllByTestId("workflow-connector");
    expect(connectors).toHaveLength(10);
    expect(connectors.filter((connector) => connector.dataset.active === "true")).toHaveLength(1);
  });

  it("keeps all graph nodes inside the visible percentage frame", () => {
    for (const node of presentationNodes) {
      expect(node.x).toBeGreaterThanOrEqual(8);
      expect(node.x).toBeLessThanOrEqual(92);
      expect(node.y).toBeGreaterThanOrEqual(34);
      expect(node.y).toBeLessThanOrEqual(78);
    }
  });

  it("renders compact run proof inside the graph", () => {
    render(
      <WorkflowGraphStage
        execution={{ completedNodeIds: ["read_docs"], currentNodeId: "reset_board" }}
        selectedNodeId={null}
        selectNode={vi.fn()}
        proof={{ runId: "run_recorded_lda_report", planLabel: "11 plan nodes", traceLabel: "3 trace frames", evidenceLabel: "JSON-RPC captured" }}
      />,
    );

    expect(screen.getByLabelText("workflow graph proof")).toHaveTextContent("run_recorded_lda_report");
    expect(screen.getByLabelText("workflow graph proof")).toHaveTextContent("11 plan nodes");
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
        proof={{ runId: "run_recorded_lda_report", planLabel: "11 plan nodes", traceLabel: "3 trace frames", evidenceLabel: "JSON-RPC evidence" }}
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
        proof={{ runId: null, planLabel: "11 plan nodes", traceLabel: "trace label", evidenceLabel: "evidence label" }}
      />,
    );

    expect(screen.getByLabelText("workflow graph proof")).toHaveTextContent("run unavailable");
    expect(screen.getByLabelText("workflow graph proof")).toHaveTextContent("trace label");
    expect(screen.getByLabelText("workflow graph proof")).toHaveTextContent("evidence label");
  });
});
