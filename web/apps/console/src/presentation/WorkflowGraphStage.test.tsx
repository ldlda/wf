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

  it("distinguishes completed, current interrupt, and future nodes semantically", () => {
    render(
      <WorkflowGraphStage
        execution={{
          completedNodeIds: ["read_docs", "build_report"],
          currentNodeId: "review_issues",
        }}
        selectedNodeId={null}
        selectNode={vi.fn()}
      />,
    );

    const readDocs = screen.getByRole("button", { name: /read documents/i });
    const buildReport = screen.getByRole("button", { name: /build report/i });
    const reviewIssues = screen.getByRole("button", { name: /issue review/i });
    const createIssues = screen.getByRole("button", { name: /create issues/i });

    expect(readDocs).toHaveAttribute("data-execution-state", "completed");
    expect(buildReport).toHaveAttribute("data-execution-state", "completed");
    expect(reviewIssues).toHaveAttribute("data-execution-state", "current");
    expect(reviewIssues).toHaveAttribute("data-current-interrupt", "true");
    expect(reviewIssues).toHaveTextContent("Current interrupt");
    expect(createIssues).toHaveAttribute("data-execution-state", "future");
  });

  it("renders connectors between nodes", () => {
    render(
      <WorkflowGraphStage
        execution={{ completedNodeIds: ["read_docs"], currentNodeId: "build_report" }}
        selectedNodeId={null}
        selectNode={vi.fn()}
      />,
    );

    const connectors = screen.getAllByTestId("workflow-connector");
    expect(connectors).toHaveLength(4);
    expect(connectors.filter((connector) => connector.dataset.active === "true")).toHaveLength(1);
  });

  it("keeps all graph nodes inside the visible percentage frame", () => {
    for (const node of presentationNodes) {
      expect(node.x).toBeGreaterThanOrEqual(14);
      expect(node.x).toBeLessThanOrEqual(86);
      expect(node.y).toBeGreaterThanOrEqual(28);
      expect(node.y).toBeLessThanOrEqual(72);
    }
  });

  it("renders compact run proof inside the graph", () => {
    render(
      <WorkflowGraphStage
        execution={{ completedNodeIds: ["read_docs"], currentNodeId: "build_report" }}
        selectedNodeId={null}
        selectNode={vi.fn()}
        proof={{ runId: "run_recorded_lda_report", traceLabel: "5 nodes", evidenceLabel: "JSON-RPC captured" }}
      />,
    );

    expect(screen.getByLabelText("workflow graph proof")).toHaveTextContent("run_recorded_lda_report");
    expect(screen.getByLabelText("workflow graph proof")).toHaveTextContent("5 nodes");
    expect(screen.getByLabelText("workflow graph proof")).toHaveTextContent("JSON-RPC captured");
  });

  it("marks compact graph mode and suppresses proof chips", () => {
    render(
      <WorkflowGraphStage
        execution={{ completedNodeIds: ["read_docs", "build_report"], currentNodeId: "review_issues" }}
        selectedNodeId={null}
        selectNode={vi.fn()}
        variant="compact"
        proof={{ runId: "run_recorded_lda_report", traceLabel: "9 workflow nodes", evidenceLabel: "JSON-RPC evidence" }}
      />,
    );

    expect(screen.getByLabelText("workflow graph")).toHaveAttribute("data-graph-variant", "compact");
    expect(screen.queryByLabelText("workflow graph proof")).not.toBeInTheDocument();
  });

  it("keeps full graph mode as the default", () => {
    render(
      <WorkflowGraphStage
        execution={{ completedNodeIds: ["read_docs"], currentNodeId: "build_report" }}
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
        proof={{ runId: null, traceLabel: "trace label", evidenceLabel: "evidence label" }}
      />,
    );

    expect(screen.getByLabelText("workflow graph proof")).toHaveTextContent("run unavailable");
    expect(screen.getByLabelText("workflow graph proof")).toHaveTextContent("trace label");
    expect(screen.getByLabelText("workflow graph proof")).toHaveTextContent("evidence label");
  });
});
