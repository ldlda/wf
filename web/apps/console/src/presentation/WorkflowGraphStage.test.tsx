import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WorkflowGraphStage } from "./WorkflowGraphStage.js";

afterEach(() => cleanup());

describe("WorkflowGraphStage", () => {
  it("renders curated workflow nodes and allows node selection", async () => {
    const selectNode = vi.fn();
    render(<WorkflowGraphStage selectedNodeId={null} selectNode={selectNode} />);

    await userEvent.click(screen.getByRole("button", { name: /issue review/i }));
    expect(selectNode).toHaveBeenCalledWith("review_issues");
  });
});
