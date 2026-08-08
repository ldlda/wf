import { describe, expect, it } from "vitest";
import {
  deriveInsertionContext,
  projectAuthoringGraph,
  type WorkbenchSelection,
} from "./authoring-graph.js";

const draft = {
  name: "review-workflow",
  start: "collect",
  steps: {
    collect: { use: "demo.collect", desc: "Collect the source material." },
    review: {
      interrupt: {
        kind: "approval",
        outcomes: ["approved", "needs_changes"],
      },
    },
  },
  routes: {
    collect: { ok: "review" },
    review: { approved: "__end__", needs_changes: "collect" },
  },
};

describe("projectAuthoringGraph", () => {
  it("projects normal, interrupt, and terminal nodes with labelled routes", () => {
    const model = projectAuthoringGraph(draft);

    expect(model.nodes.map((node) => [node.id, node.data.kind])).toEqual([
      ["__end__", "end"],
      ["collect", "use"],
      ["review", "interrupt"],
    ]);
    expect(model.edges.map((edge) => [edge.id, edge.source, edge.label, edge.target])).toEqual([
      ["e-collect-review-0", "collect", "ok", "review"],
      ["e-review-__end__-1", "review", "approved", "__end__"],
      ["e-review-collect-2", "review", "needs_changes", "collect"],
    ]);
    expect(model.nodes.find((node) => node.id === "collect")?.data.nodeRef).toBe(
      "demo.collect",
    );
  });

  it("keeps projection ids and positions stable when step insertion order changes", () => {
    const reordered = {
      ...draft,
      steps: { review: draft.steps.review, collect: draft.steps.collect },
      routes: { review: draft.routes.review, collect: draft.routes.collect },
    };

    expect(projectAuthoringGraph(reordered)).toEqual(projectAuthoringGraph(draft));
  });
});

describe("WorkbenchSelection", () => {
  it("derives explicit route insertion only from a selected connector", () => {
    const edgeSelection: WorkbenchSelection = {
      kind: "edge",
      stepId: "review",
      outcome: "approved",
    };

    expect(deriveInsertionContext(edgeSelection)).toEqual({
      routeFromStep: "review",
      routeFromOutcome: "approved",
    });
  });

  it("keeps node insertion connected to a step without inventing an outcome", () => {
    expect(deriveInsertionContext({ kind: "node", nodeId: "collect" })).toEqual({
      routeFromStep: "collect",
    });
  });

  it("does not derive insertion context from canvas or capability selection", () => {
    expect(deriveInsertionContext({ kind: "canvas" })).toBeNull();
    expect(
      deriveInsertionContext({ kind: "capability", qualifiedName: "demo.collect" }),
    ).toBeNull();
  });
});
