import { describe, expect, it } from "vitest";
import { architectureCatalog } from "./architecture-catalog.js";

const figure = (id: string) => {
  const result = architectureCatalog.figures.find((candidate) => candidate.id === id);
  if (!result) throw new Error(`missing architecture figure: ${id}`);
  return result;
};

describe("architectureCatalog", () => {
  it("keeps the thesis architecture spine as the root contract", () => {
    const root = figure(architectureCatalog.rootFigureId);
    expect(root.layout.kind).toBe("explicit");
    if (root.layout.kind !== "explicit") throw new Error("architecture overview must use authored positions");
    expect(root.layout.positions["node-use"]?.x).toBeGreaterThan(
      root.layout.positions["core-runtime"]?.x ?? 0,
    );
    expect(root.nodes.map((node) => node.label)).toEqual(expect.arrayContaining([
      "Front door and transport",
      "Workflow API operations",
      "WorkflowServer composition",
      "wf_core execution loop",
      "Lifecycle records",
      "Capability inventory",
    ]));
  });

  it("declares subject-appropriate topologies instead of repeated linear flows", () => {
    expect(figure("client-surface-detail").layout.kind).toBe("fan-in");
    expect(figure("workflow-api-detail").layout.kind).toBe("hub");
    expect(figure("core-runtime-detail").layout.kind).toBe("flow");
    expect(figure("node-use-detail").layout.kind).toBe("explicit");
    expect(figure("configured-provider-detail").layout.kind).toBe("fan-in");
  });

  it("models the supported kernel branches and the provider-neutral boundary", () => {
    const kernel = figure("core-runtime-detail");
    expect(kernel.nodes.map((node) => node.label)).toEqual(expect.arrayContaining([
      "Select ready frame",
      "Step kind",
      "Append trace frame",
      "Route by outcome",
    ]));
    const stepKinds = figure("step-kind-detail");
    expect(stepKinds.nodes.map((node) => node.label)).toEqual(expect.arrayContaining([
      "NodeUse",
      "Condition",
      "Foreach",
      "Join",
      "Subgraph",
      "Interrupt",
      "End",
    ]));
    const providers = figure("configured-provider-detail");
    expect(providers.nodes.map((node) => node.label)).toEqual(expect.arrayContaining([
      "Capability inventory",
      "Built-in sources",
      "MCP sources",
      "Python sources",
    ]));
    expect(providers.edges.some((edge) => edge.from === "builtin-sources" && edge.to === "capability-inventory")).toBe(true);
    expect(providers.edges.some((edge) => edge.from === "mcp-sources" && edge.to === "capability-inventory")).toBe(true);
    expect(providers.edges.some((edge) => edge.from === "python-sources" && edge.to === "capability-inventory")).toBe(true);
  });

  it("keeps NodeUse as an explicit participant sequence with factual evidence", () => {
    const sequence = figure("node-use-detail");
    expect(sequence.nodes.map((node) => node.label)).toEqual([
      "Runtime",
      "Binding Resolver",
      "NodeDef Handler",
      "State Reducers",
      "Trace Store",
    ]);
    expect(sequence.nodes.every((node) => node.evidence !== undefined)).toBe(true);
  });

  it("keeps WorkflowApi nodes concise and moves operation facts into evidence spotlights", () => {
    const api = figure("workflow-api-detail");
    const operationIds = [
      "capability-operations",
      "draft-operations",
      "artifact-operations",
      "deployment-operations",
      "run-operations",
    ];

    for (const nodeId of operationIds) {
      const node = api.nodes.find((candidate) => candidate.id === nodeId);
      expect(node?.details, nodeId).toBeUndefined();
      expect(node?.evidence?.facts?.length, nodeId).toBeGreaterThan(0);
      expect(node?.evidence?.codePointer, nodeId).toMatch(/^src\//);
    }
  });
});
