import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { DraftWorkspace } from "../domain/draft-workspace-models.js";
import { AuthoringGraph } from "./AuthoringGraph.js";
import type { WorkbenchSelection } from "./authoring-graph.js";

const workspace: DraftWorkspace = {
  workspaceId: "draft-review",
  revision: 2,
  title: "Review workflow",
  status: "invalid",
  diagnostics: [],
  summary: {
    name: "review-workflow",
    start: "collect",
    stepCount: 2,
    routeCount: 2,
    steps: ["collect", "review"],
  },
  draft: {
    name: "review-workflow",
    start: "collect",
    steps: {
      collect: { use: "demo.collect" },
      review: { interrupt: { kind: "approval" } },
    },
    routes: { collect: { ok: "review" }, review: { submitted: "__end__" } },
  },
};

afterEach(() => cleanup());

describe("AuthoringGraph", () => {
  it("renders the projected graph and marks the selected node", () => {
    const selection: WorkbenchSelection = { kind: "node", nodeId: "review" };
    const { container } = render(
      <AuthoringGraph draft={workspace.draft} selection={selection} onSelectionChange={vi.fn()} />,
    );

    expect(screen.getAllByText("collect")).not.toHaveLength(0);
    expect(screen.getByText("approval")).toBeInTheDocument();
    expect(container.querySelector('[data-node-id="review"]')).toHaveAttribute(
      "data-active",
      "true",
    );
    expect(container.querySelector('[data-node-id="review"]')).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("selects a connector by its source step and outcome", () => {
    const onSelectionChange = vi.fn<(selection: WorkbenchSelection) => void>();
    const { container } = render(
      <AuthoringGraph draft={workspace.draft} selection={{ kind: "canvas" }} onSelectionChange={onSelectionChange} />,
    );

    const edgeButton = container.querySelector('[data-edge-id="e-7:collect2:ok6:review"]');
    expect(edgeButton).not.toBeNull();
    fireEvent.click(edgeButton!);

    expect(onSelectionChange).toHaveBeenCalledWith({
      kind: "edge",
      stepId: "collect",
      outcome: "ok",
    });
  });
});
