import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { discussionBranches } from "../storyboard.js";
import { projectDefenseDiscussionGroups } from "./defense-discussion-index.js";
import { DefenseDiscussionIndex } from "./DefenseDiscussionIndex.js";

describe("DefenseDiscussionIndex", () => {
  afterEach(cleanup);

  it("renders seven labelled topic sections and every canonical branch title", () => {
    render(<DefenseDiscussionIndex discussionBranches={discussionBranches} openDiscussion={vi.fn()} />);

    const nav = screen.getByRole("navigation", { name: "defense discussion index" });
    expect(within(nav).getAllByRole("heading", { level: 2 })).toHaveLength(7);
    for (const group of projectDefenseDiscussionGroups(discussionBranches)) {
      const heading = within(nav).getByRole("heading", { name: group.label, level: 2 });
      expect(heading.querySelector("svg")).not.toBeNull();
    }
    for (const branch of discussionBranches) {
      expect(within(nav).getByRole("button", { name: branch.title })).toBeInTheDocument();
    }
  });

  it("opens the canonical branch selected from the index", () => {
    const openDiscussion = vi.fn();
    render(<DefenseDiscussionIndex discussionBranches={discussionBranches} openDiscussion={openDiscussion} />);

    fireEvent.click(screen.getByRole("button", { name: "Live demo reliability" }));

    expect(openDiscussion).toHaveBeenCalledWith("demo-reliability");
  });
});
