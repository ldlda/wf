import { describe, expect, it } from "vitest";
import {
  decodeCapabilityCallResult,
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
      capabilities: [
        {
          kind: "node_spec",
          name: "local.docs.read",
          sourceId: "local.docs",
          description: null,
          outcomes: ["ok", "error"],
          inputFields: ["names"],
          outputFields: ["documents"],
          isAsync: false,
        },
        {
          kind: "wrapper_artifact",
          name: "local.reports.build",
          sourceId: "local.reports",
          description: "Build a report.",
          outcomes: ["ok"],
          inputFields: [],
          outputFields: ["report"],
          isAsync: true,
          artifactId: "reports",
          title: "Reports",
          version: 2,
        },
      ],
      nextCursor: null,
      total: 2,
    });

    expect(page.capabilities[0]?.kind).toBe("node_spec");
    expect(page.capabilities[1]?.kind).toBe("wrapper_artifact");
    expect(page.capabilities[0]?.description).toBeNull();
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

  it("decodes a successful capability call with dependency diagnostics", () => {
    const result = decodeCapabilityCallResult({
      qualifiedName: "local.docs.read_documents",
      sourceId: "local.docs",
      kind: "node_spec",
      deploymentId: null,
      outcome: "ok",
      output: { documents: [{ name: "README.md" }] },
      diagnostics: [
        {
          boundSource: "local.docs",
          code: "source_missing",
          logicalRef: "local.docs",
          message: "The source is not configured.",
          repairHint: "Configure the source before calling.",
          severity: "error",
        },
      ],
    });

    expect(result.qualifiedName).toBe("local.docs.read_documents");
    expect(result.output).toEqual({ documents: [{ name: "README.md" }] });
    expect(result.diagnostics[0]?.repairHint).toBe(
      "Configure the source before calling.",
    );
  });

  it("decodes runtime_error as a normal completed capability result", () => {
    const result = decodeCapabilityCallResult({
      qualifiedName: "local.docs.read_documents",
      sourceId: "local.docs",
      kind: "wrapper_artifact",
      deploymentId: "docs.default",
      outcome: "runtime_error",
      output: null,
      diagnostics: [],
    });

    expect(result.outcome).toBe("runtime_error");
    expect(result.output).toBeNull();
  });

  it("rejects malformed capability call results", () => {
    expect(() => decodeCapabilityCallResult({ outcome: "ok" })).toThrow(
      "CapabilityCallResult is malformed",
    );
  });
});
