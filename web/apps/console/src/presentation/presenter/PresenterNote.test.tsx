import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { PresenterNote } from "./PresenterNote.js";
import { presenterNotes } from "./presenter-notes.js";

afterEach(cleanup);

describe("PresenterNote", () => {
  it("renders the rehearsal hierarchy and preserves note metadata", () => {
    const note = presenterNotes.find(
      (candidate) => candidate.sceneId === "run-from-deployment" && candidate.beatId === "operation",
    );
    const next = presenterNotes.find(
      (candidate) => candidate.sceneId === "run-from-deployment" && candidate.beatId === "graph",
    );
    if (!note || !next) throw new Error("missing run-from-deployment presenter notes");

    render(
      <PresenterNote
        note={note}
        cumulativeSeconds={23}
        next={next}
        covered={false}
        onCoveredChange={() => {}}
      />,
    );

    expect(screen.getByRole("region", { name: "Beat goal" })).toHaveTextContent(note.goal);

    const anchors = screen.getByRole("region", { name: "Anchor terms" });
    const anchorList = within(anchors).getByRole("list");
    for (const keyword of note.keywords) {
      expect(anchorList).toHaveTextContent(keyword);
    }

    const wording = screen.getByRole("region", { name: "Suggested wording" });
    expect(wording).toHaveTextContent(note.mustSay.replaceAll("**", ""));
    expect(within(wording).getByText("workflow.runs.start").tagName).toBe("STRONG");

    expect(screen.queryByText("Must say")).not.toBeInTheDocument();
    expect(screen.getByText(`Evidence (${note.evidencePointers.length})`)).toBeInTheDocument();
    expect(screen.getByText(`Linked Q&A (${note.qnaBranchIds.length})`)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to next beat" })).toHaveAttribute(
      "href",
      "#scene/run-from-deployment/graph",
    );
  });
});
