import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { DemoRunFacts } from "./demo-run-facts.js";

afterEach(() => cleanup());
import {
  InterruptPayloadFacts,
  RunInputFacts,
  RunOutputFacts,
  RunResumeFacts,
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

const makeCreatedFacts = (markdown: string): DemoRunFacts => ({
  ...baseFacts,
  output: {
    state: "created",
    output: {
      approved: true,
      markdown,
      created_issues: [{ id: "ISSUE-001", title: "Prepare defense", url: "local://issue-board/ISSUE-001" }],
      selected_issue_ids: ["risk-1"],
      comment: "Create the selected issue.",
    },
    createdIssues: [{ id: "ISSUE-001", title: "Prepare defense", url: "local://issue-board/ISSUE-001" }],
    markdownPreview: markdown,
  },
});

const makeTraceFacts = (count: number): DemoRunFacts => ({
  ...baseFacts,
  trace: {
    frames: Array.from({ length: count }, (_, index) => ({
      nodeId: `node-${index}`,
      stepType: index === 3 ? "interrupt" : "node",
      outcome: index === 3 ? "submitted" : "ok",
      resolvedInputLabel: "captured as empty object",
      outputLabel: "captured as empty object",
      stateChangesLabel: "captured as empty object",
    })),
  },
});

describe("RunInputFacts", () => {
  it("renders workflow input facts with selected documents and board path", () => {
    render(<RunInputFacts facts={baseFacts} />);

    expect(screen.getByText("Workflow input")).toBeDefined();
    expect(screen.getByText("project-brief.md")).toBeDefined();
    expect(screen.getByText("architecture-notes.md")).toBeDefined();
    expect(screen.getByText("issue-board.json")).toBeDefined();
  });
});

describe("InterruptPayloadFacts", () => {
  it("renders interrupt payload as a scrollable report and proposed issue list", () => {
    const facts: DemoRunFacts = {
      ...baseFacts,
      interrupt: {
        ...baseFacts.interrupt,
        reportMarkdownPreview: "# Long report\n\nThe workflow substrate is ready.\n\n## Evidence\n\n- Draft\n- Artifact\n- Deployment\n- Run",
        proposedIssues: [
          { id: "risk-1", title: "Prepare defense", body: "Rehearse.", severity: "medium" },
        ],
      },
    };

    render(<InterruptPayloadFacts facts={facts} />);

    expect(screen.getByRole("region", { name: /interrupt report markdown/i })).toHaveTextContent("Long report");
    expect(screen.getByText("risk-1")).toBeInTheDocument();
    expect(screen.getByText(/submitted/)).toBeInTheDocument();
    expect(screen.getByText(/cancelled/)).toBeInTheDocument();
  });
});

describe("RunResumeFacts", () => {
  it("renders resume payload separately from output", () => {
    const facts: DemoRunFacts = {
      ...baseFacts,
      resume: {
        outcome: "submitted",
        payload: {
          approved: true,
          selected_issue_ids: ["risk-1"],
          comment: "Create the selected issue.",
        },
      },
    };

    render(<RunResumeFacts facts={facts} />);

    expect(screen.getByText("submitted")).toBeInTheDocument();
    expect(screen.getByText("risk-1")).toBeInTheDocument();
    expect(screen.getByText("Create the selected issue.")).toBeInTheDocument();
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
    expect(screen.getByRole("region", { name: /workflow markdown output/i })).toBeInTheDocument();
  });

  it("renders output report as the primary scroll region", () => {
    const createdFacts = makeCreatedFacts("# Report\n\n" + "body\n".repeat(40));

    render(<RunOutputFacts facts={createdFacts} priority="report" />);

    expect(screen.getByRole("region", { name: /workflow markdown output/i })).toHaveClass("run-facts-scroll-region");
    expect(screen.getByText("ISSUE-001")).toBeInTheDocument();
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

  it("renders trace frames inside a scrollable list", () => {
    const traceFacts = makeTraceFacts(8);

    render(<RunTraceFacts facts={traceFacts} />);

    expect(screen.getByRole("region", { name: /workflow trace frames/i })).toHaveClass("run-facts-scroll-region");
    expect(screen.getByText("node-7")).toBeInTheDocument();
  });
});
