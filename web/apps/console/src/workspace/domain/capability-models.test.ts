import { describe, expect, it } from "vitest";
import {
  decodeCapabilityDetail,
  decodeCapabilityPage,
} from "./capability-models.js";

const wrapperHints = {
  confidence: "high",
  notes: [],
};

describe("capability models", () => {
  it("preserves discriminated node and wrapper summaries", () => {
    const page = decodeCapabilityPage({
      items: [
        {
          kind: "node_spec",
          name: "local.docs.read",
          sourceId: "local.docs",
          description: null,
          outcomes: ["ok", "error"],
          inputFields: ["names"],
          outputFields: ["documents"],
        },
        {
          kind: "wrapper_artifact",
          name: "local.reports.build",
          sourceId: "local.reports",
          description: "Build a report.",
          outcomes: ["ok"],
          inputFields: [],
          outputFields: ["report"],
        },
      ],
      nextCursor: null,
      total: 2,
    });

    expect(page.items[0]?.kind).toBe("node_spec");
    expect(page.items[1]?.kind).toBe("wrapper_artifact");
    expect(page.items[0]?.description).toBeNull();
  });

  it("decodes nullable detail fields for both capability kinds", () => {
    const node = decodeCapabilityDetail({
      kind: "node_spec",
      name: "local.docs.read",
      sourceId: "local.docs",
      description: null,
      isAsync: false,
      outcomes: ["ok"],
      inputSchema: {},
      outputSchema: {},
      wrapperHints,
      acceptsContext: false,
    });
    const wrapper = decodeCapabilityDetail({
      kind: "wrapper_artifact",
      name: "local.reports.build",
      sourceId: "local.reports",
      description: null,
      isAsync: true,
      outcomes: ["ok"],
      inputSchema: {},
      outputSchema: {},
      wrapperHints,
      artifactId: "reports",
      title: "Reports",
      version: 2,
      requiredCapabilities: {},
    });

    expect(node.kind).toBe("node_spec");
    expect(wrapper.kind).toBe("wrapper_artifact");
    if (wrapper.kind === "wrapper_artifact") {
      expect(wrapper.version).toBe(2);
    }
  });
});
