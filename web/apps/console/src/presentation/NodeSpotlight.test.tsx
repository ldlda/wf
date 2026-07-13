import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { NodeSpotlight } from "./NodeSpotlight.js";

afterEach(() => cleanup());

describe("NodeSpotlight", () => {
  it("shows the interrupt contract as a factual reusable inspector", () => {
    render(<NodeSpotlight nodeId="review_issues" close={vi.fn()} />);

    expect(screen.getByRole("dialog", { name: "Review issues" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Review issues" })).toBeInTheDocument();
    expect(screen.getAllByText("Human boundary")).toHaveLength(2);
    expect(screen.getByText(/issue_review/)).toBeInTheDocument();
    expect(screen.getByText(/request: issue proposals/i)).toBeInTheDocument();
    expect(screen.getByText(/submitted issues or revision request/i)).toBeInTheDocument();
    expect(screen.getByText("submitted")).toBeInTheDocument();
    expect(screen.getByText("cancelled")).toBeInTheDocument();
    expect(screen.getByText("workflow interrupt: issue_review")).toBeInTheDocument();
  });

  it("distinguishes an issue-creation action from an ordinary node", () => {
    const { unmount } = render(<NodeSpotlight nodeId="create_issues" close={vi.fn()} />);

    expect(screen.getByRole("heading", { name: "Create issues" })).toBeInTheDocument();
    expect(screen.getByText("Action")).toBeInTheDocument();
    expect(screen.getByText("Issue board source")).toBeInTheDocument();
    expect(screen.getByText(/submitted issues/i)).toBeInTheDocument();
    expect(screen.getByText(/persisted issue-board entries/i)).toBeInTheDocument();
    expect(screen.getByText("local.issue_board.create_issues")).toBeInTheDocument();
    unmount();

    render(<NodeSpotlight nodeId="read_docs" close={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "Read documents" })).toBeInTheDocument();
    expect(screen.getByText("document source")).toBeInTheDocument();
    expect(screen.getByText("local.lda_docs.read_documents")).toBeInTheDocument();
  });
});
