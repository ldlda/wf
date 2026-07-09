import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { DemoRunFacts } from "./demo-run-facts.js";
import {
  RunInputFacts,
  RunOutputFacts,
  RunTraceFacts,
} from "./RunFactsPanel.js";

const baseFacts: DemoRunFacts = {
  input: {
    selectedDocuments: ["project-brief.md", "architecture-notes.md"],
    boardPath: "issue-board.json",
  },
  interrupt: {
    kind: "issue_review",
    typed: true,
    outcomes: ["submitted", "cancelled"],
    proposedIssues: [],
    reportMarkdownPreview: "",
  },
  resume: { outcome: null, payload: null },
  output: { state: "not-created", message: "Output not created yet" },
  trace: { frames: [] },
};

describe("RunInputFacts", () => {
  it("renders workflow input facts with selected documents and board path", () => {
    render(<RunInputFacts facts={baseFacts} />);

    expect(screen.getByText("Workflow input")).toBeDefined();
    expect(screen.getByText("project-brief.md")).toBeDefined();
    expect(screen.getByText("architecture-notes.md")).toBeDefined();
    expect(screen.getByText("issue-board.json")).toBeDefined();
  });
});

describe("RunOutputFacts", () => {
  it("renders output not created yet before resume", () => {
    render(<RunOutputFacts facts={baseFacts} />);

    expect(screen.getByText("Output not created yet")).toBeDefined();
  });

  it("renders created output facts with issue details", () => {
    const createdFacts: DemoRunFacts = {
      ...baseFacts,
      output: {
        state: "created",
        output: {
          approved: true,
          markdown: "# Report",
          created_issues: [
            { id: "ISSUE-001", title: "Prepare defense", url: "local://issue-board/ISSUE-001" },
          ],
          selected_issue_ids: ["risk-1"],
          comment: "Create the selected issue.",
        },
        createdIssues: [
          { id: "ISSUE-001", title: "Prepare defense", url: "local://issue-board/ISSUE-001" },
        ],
        markdownPreview: "# Report",
      },
    };

    render(<RunOutputFacts facts={createdFacts} />);

    expect(screen.getByText("ISSUE-001")).toBeDefined();
    expect(screen.getByText("local://issue-board/ISSUE-001")).toBeDefined();
    expect(screen.getByText("Create the selected issue.")).toBeDefined();
  });
});

describe("RunTraceFacts", () => {
  it("renders trace frame node IDs and empty object labels", () => {
    const traceFacts: DemoRunFacts = {
      ...baseFacts,
      output: {
        state: "created",
        output: {
          approved: true,
          markdown: "# Report",
          created_issues: [],
          selected_issue_ids: [],
          comment: null,
        },
        createdIssues: [],
        markdownPreview: "# Report",
      },
      trace: {
        frames: [
          {
            nodeId: "list_documents",
            stepType: "node",
            outcome: "ok",
            resolvedInputLabel: "captured as empty object",
            outputLabel: "captured as empty object",
            stateChangesLabel: "captured as empty object",
          },
          {
            nodeId: "review_issues",
            stepType: "interrupt",
            outcome: "submitted",
            resolvedInputLabel: "captured as empty object",
            outputLabel: "captured as empty object",
            stateChangesLabel: "captured as empty object",
          },
        ],
      },
    };

    render(<RunTraceFacts facts={traceFacts} />);

    expect(screen.getByText("list_documents")).toBeDefined();
    expect(screen.getByText("review_issues")).toBeDefined();
    expect(screen.getAllByText("captured as empty object").length).toBeGreaterThanOrEqual(2);
  });
});
