import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WorkflowGraphStage } from "./WorkflowGraphStage.js";

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
});
