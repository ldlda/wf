import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { DraftWorkspace } from "../domain/draft-workspace-models.js";
import { DraftWorkbench } from "./DraftWorkbench.js";

const workspace: DraftWorkspace = {
  workspaceId: "draft-review",
  revision: 2,
  title: "Review workflow",
  status: "invalid",
  diagnostics: [
    {
      code: "missing_route",
      path: "routes.review",
      message: "Review needs a route.",
      stepId: "review",
      repairHint: "Add a submitted route.",
      details: {},
    },
  ],
  summary: {
    name: "review-workflow",
    start: "collect",
    stepCount: 2,
    routeCount: 1,
    steps: ["collect", "review"],
  },
  draft: {
    name: "review-workflow",
    start: "collect",
    steps: { collect: { use: "demo.collect" }, review: { interrupt: { kind: "approval" } } },
    routes: { collect: { ok: "review" } },
  },
};

afterEach(() => cleanup());

describe("DraftWorkbench", () => {
  it("keeps palette, graph, and inspector visible in the desktop shell", () => {
    render(
      <DraftWorkbench
        draft={workspace}
        capabilities={[
          {
            kind: "node_spec",
            name: "demo.collect",
            sourceId: "demo",
            description: "Collect source material.",
            outcomes: ["ok"],
            inputFields: [],
            outputFields: [],
          },
        ]}
      />,
    );

    expect(screen.getByRole("region", { name: "Capability palette" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Workflow graph" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Context inspector" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "demo.collect" })).toBeInTheDocument();
    expect(screen.getByText("Draft summary")).toBeInTheDocument();
    expect(screen.getByText("Review needs a route.")).toBeInTheDocument();
  });

  it("keeps the raw draft collapsed and exposes all deferred actions without handlers", () => {
    render(<DraftWorkbench draft={workspace} />);

    const raw = screen.getByText("Raw draft document").closest("details");
    expect(raw).not.toHaveAttribute("open");
    for (const label of [
      "Undo — Later",
      "Redo — Later",
      "Delete node — Later",
      "Delete route — Later",
      "Add other step — Later",
      "Create artifact — Later",
    ]) {
      expect(screen.getByRole("button", { name: label })).toBeDisabled();
    }
  });
});
