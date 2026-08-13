import { describe, expect, it } from "vitest";
import type { DraftDiagnostic, DraftWorkspace } from "../domain/draft-workspace-models.js";
import {
  bindingDiagnosticsForStep,
  capabilityLocalPathSuggestions,
  inferredStateSchemaPreview,
  isJsonValue,
  inputBindingRows,
  outputBindingRows,
  projectSelectedStepDataflow,
  serializeInputBindingRow,
  serializeInputBindingRows,
  serializeOutputBindingRow,
  serializeOutputBindingRows,
  stateTargetSuggestions,
  workflowSourceSuggestions,
} from "./selected-step-dataflow.js";

const summary = {
  name: "report",
  start: "render",
  stepCount: 1,
  routeCount: 0,
  steps: ["render"],
};

const bindings = {
  input: [
    { path: "input.items", target: "items" },
    { target: "separator", value: null },
    { path: "state.fallback", target: "fallback" },
  ],
  output: [
    { source: "text", target: "state.report" },
    { source: "text", target: "state.audit.latest" },
  ],
};

const keyedDraft: DraftWorkspace = {
  workspaceId: "draft-report",
  revision: 3,
  title: "Report",
  status: "valid",
  diagnostics: [],
  summary,
  draft: {
    steps: {
      render: {
        use: "wf.std.concat",
        ...bindings,
        retry: 0,
      },
    },
  },
};

const compiledDraft: DraftWorkspace = {
  ...keyedDraft,
  draft: { nodes: [{ id: "render", type: "node", node: "wf.std.concat", ...bindings, retry: 0 }] },
};

const schema = {
  type: "object",
  properties: {
    items: { type: "array", items: { type: "string" } },
    account: {
      type: "object",
      properties: { name: { type: "string" } },
    },
  },
};

const diagnostic = (
  path: string,
  stepId: string | null = null,
): DraftDiagnostic => ({
  code: `diagnostic-${path}`,
  path,
  message: `Issue at ${path}`,
  stepId,
  repairHint: null,
  details: {},
});

describe("selected-step dataflow projection", () => {
  it("projects keyed and compiled drafts to the same ordered canonical dataflow", () => {
    const keyed = projectSelectedStepDataflow(keyedDraft, "render");
    const compiled = projectSelectedStepDataflow(compiledDraft, "render");

    expect(keyed).toEqual({
      stepId: "render",
      compiledNodeIndex: null,
      capabilityName: "wf.std.concat",
      description: undefined,
      retry: 0,
      timeoutSeconds: undefined,
      inputs: bindings.input,
      outputs: bindings.output,
      unsupported: [],
    });
    expect(compiled).toEqual({
      ...keyed,
      compiledNodeIndex: 0,
    });
  });

  it("keeps one composite expression as one input binding and preserves its legacy row index", () => {
    const composite = {
      target: "items",
      expression: {
        kind: "array",
        items: [
          { kind: "path", path: "state.foo" },
          { kind: "literal", value: "wowcool" },
        ],
      },
    };
    const projected = projectSelectedStepDataflow({
      ...keyedDraft,
      draft: {
        steps: {
          render: { use: "wf.std.concat", input: [bindings.input[0], composite, bindings.input[1]] },
        },
      },
    }, "render");

    expect(projected?.inputs).toHaveLength(3);
    expect(projected?.inputs[1]).toEqual(composite);
    expect(inputBindingRows([bindings.input[0], composite, bindings.input[1]])).toEqual([
      expect.objectContaining({ kind: "canonical", index: 0 }),
      expect.objectContaining({ kind: "unsupported", index: 1, raw: composite }),
      expect.objectContaining({ kind: "canonical", index: 2 }),
    ]);
  });

  it("accepts structural paths, whole-payload paths, empty lists, and reports malformed rows", () => {
    const draft: DraftWorkspace = {
      ...keyedDraft,
      draft: {
        steps: {
          render: {
            use: "wf.std.concat",
            input: [
              {
                path: { root: "input", parts: ["items"] },
                target: { root: "local", parts: [] },
              },
              { target: "broken", path: { root: "input", parts: [""] } },
              { target: "literal", value: null },
              null,
            ],
            output: [
              { source: { root: "local", parts: [] }, target: { root: "state", parts: ["report"] } },
              { source: "text", target: "state" },
              { source: "text", target: "state." },
              { source: "text", target: "state.audit..latest" },
            ],
          },
        },
      },
    };

    const projected = projectSelectedStepDataflow(draft, "render");
    expect(projected?.inputs).toEqual([
      { path: { root: "input", parts: ["items"] }, target: { root: "local", parts: [] } },
      { target: "literal", value: null },
    ]);
    expect(projected?.outputs).toEqual([
      { source: { root: "local", parts: [] }, target: { root: "state", parts: ["report"] } },
    ]);
    expect(projected?.unsupported).toEqual([
      expect.objectContaining({ field: "input", index: 1, raw: draft.draft && expect.anything() }),
      expect.objectContaining({ field: "input", index: 3 }),
      expect.objectContaining({ field: "output", index: 1 }),
      expect.objectContaining({ field: "output", index: 2 }),
      expect.objectContaining({ field: "output", index: 3 }),
    ]);
    expect(projected?.unsupported.every((row) => row.reason.length > 0)).toBe(true);

    expect(projectSelectedStepDataflow({ ...keyedDraft, draft: { steps: { render: { use: "x", input: [], output: [] } } } }, "render")).toEqual({
      stepId: "render",
      compiledNodeIndex: null,
      capabilityName: "x",
      description: undefined,
      retry: undefined,
      timeoutSeconds: undefined,
      inputs: [],
      outputs: [],
      unsupported: [],
    });
  });

  it("preserves malformed binding containers and extra row keys for keyed and compiled steps", () => {
    const extraInput = { path: "input.items", target: "items", extra: true };
    const extraOutput = { source: "text", target: "state.report", extra: true };
    expect(inputBindingRows(undefined)).toEqual([]);
    expect(inputBindingRows(null)).toEqual([
      expect.objectContaining({ kind: "unsupported", index: 0, raw: null }),
    ]);
    expect(inputBindingRows({ path: "input.items", target: "items" })).toEqual([
      expect.objectContaining({ kind: "unsupported", index: 0 }),
    ]);
    expect(inputBindingRows([extraInput])).toEqual([
      expect.objectContaining({ kind: "unsupported", index: 0, raw: extraInput }),
    ]);
    expect(outputBindingRows(null)).toEqual([
      expect.objectContaining({ kind: "unsupported", index: 0, raw: null }),
    ]);
    expect(outputBindingRows({ source: "text", target: "state.report" })).toEqual([
      expect.objectContaining({ kind: "unsupported", index: 0 }),
    ]);
    expect(outputBindingRows([extraOutput])).toEqual([
      expect.objectContaining({ kind: "unsupported", index: 0, raw: extraOutput }),
    ]);

    const keyed = projectSelectedStepDataflow({
      ...keyedDraft,
      draft: { steps: { render: { use: "wf.std.concat", input: null, output: extraOutput } } },
    }, "render");
    const compiled = projectSelectedStepDataflow({
      ...compiledDraft,
      draft: { nodes: [{ id: "render", node: "wf.std.concat", input: extraInput, output: null }] },
    }, "render");

    expect(keyed?.inputs).toEqual([]);
    expect(keyed?.outputs).toEqual([]);
    expect(keyed?.unsupported.map(({ field, index, raw }) => ({ field, index, raw }))).toEqual([
      { field: "input", index: 0, raw: null },
      { field: "output", index: 0, raw: extraOutput },
    ]);
    expect(compiled?.inputs).toEqual([]);
    expect(compiled?.outputs).toEqual([]);
    expect(compiled?.unsupported.map(({ field, index, raw }) => ({ field, index, raw }))).toEqual([
      { field: "input", index: 0, raw: extraInput },
      { field: "output", index: 0, raw: null },
    ]);
  });

  it("returns null for a missing step", () => {
    expect(projectSelectedStepDataflow(keyedDraft, "missing")).toBeNull();
  });

  it("keeps unsupported rows at their original positions for explicit repair", () => {
    const rawInput = [
      { path: "input.first", target: "first" },
      { target: "broken", value: undefined },
      { path: "input.third", target: "third" },
    ];
    const rawOutput = [
      { source: "first", target: "state.first" },
      { source: "broken", target: "state" },
      { source: "third", target: "state.third" },
    ];

    expect(inputBindingRows(rawInput)).toEqual([
      { kind: "canonical", index: 0, value: rawInput[0] },
      expect.objectContaining({ kind: "unsupported", index: 1, raw: rawInput[1] }),
      { kind: "canonical", index: 2, value: rawInput[2] },
    ]);
    expect(outputBindingRows(rawOutput)).toEqual([
      { kind: "canonical", index: 0, value: rawOutput[0] },
      expect.objectContaining({ kind: "unsupported", index: 1, raw: rawOutput[1] }),
      { kind: "canonical", index: 2, value: rawOutput[2] },
    ]);

    const inputRows = inputBindingRows(rawInput);
    const outputRows = outputBindingRows(rawOutput);
    expect(serializeInputBindingRows(inputRows)).toBeNull();
    expect(serializeOutputBindingRows(outputRows)).toBeNull();
    expect(serializeInputBindingRows(inputRows.filter((row) => row.kind === "canonical"))).toEqual([
      rawInput[0],
      rawInput[2],
    ]);
    expect(serializeOutputBindingRows(outputRows.filter((row) => row.kind === "canonical"))).toEqual([
      rawOutput[0],
      rawOutput[2],
    ]);
  });

  it("serializes canonical strings and rejects invalid output state targets", () => {
    expect(serializeInputBindingRow({
      path: { root: "input", parts: ["items"] },
      target: { root: "local", parts: [] },
    })).toEqual({ path: "input.items", target: "." });
    expect(serializeInputBindingRow({ target: "separator", value: null })).toEqual({
      target: "separator",
      value: null,
    });
    expect(serializeOutputBindingRow({
      source: { root: "local", parts: [] },
      target: { root: "state", parts: ["audit", "latest"] },
    })).toEqual({ source: ".", target: "state.audit.latest" });

    for (const target of ["state", "state.", "state.audit..latest", { root: "state", parts: [] }]) {
      expect(serializeOutputBindingRow({ source: "text", target })).toBeNull();
    }
  });

  it("accepts finite recursive JSON literals and rejects non-JSON values", () => {
    const valid = {
      target: "payload",
      value: { count: 0, enabled: false, nested: [null, "ok", { ratio: -2.5 }] },
    };
    expect(isJsonValue(valid.value)).toBe(true);
    expect(serializeInputBindingRow(valid)).toEqual(valid);

    const invalidValues: unknown[] = [
      undefined,
      Number.NaN,
      Number.POSITIVE_INFINITY,
      Number.NEGATIVE_INFINITY,
      () => "not JSON",
      Symbol("not JSON"),
      ["ok", undefined],
      { nested: Number.NaN },
      new Date("2026-08-09T00:00:00.000Z"),
    ];
    for (const value of invalidValues) {
      expect(isJsonValue(value)).toBe(false);
      expect(serializeInputBindingRow({ target: "payload", value })).toBeNull();
    }
  });
});

describe("selected-step schema helpers", () => {
  it("returns canonical schema path suggestions", () => {
    expect(workflowSourceSuggestions(schema, {
      type: "object",
      properties: { fallback: { type: "string" } },
    })).toEqual([
      "input.items",
      "input.items.0",
      "input.account",
      "input.account.name",
      "state.fallback",
    ]);
    expect(capabilityLocalPathSuggestions(schema)).toEqual([
      ".",
      "items",
      "items.0",
      "account",
      "account.name",
    ]);
    expect(stateTargetSuggestions(schema)).toEqual(["state.items", "state.items.0", "state.account", "state.account.name"]);
  });

  it("combines workflow input and state source suggestions with nested local targets", () => {
    expect(workflowSourceSuggestions(
      { type: "object", properties: { request: { type: "object", properties: { id: { type: "string" } } } } },
      { type: "object", properties: { session: { type: "object", properties: { token: { type: "string" } } } } },
    )).toEqual(["input.request", "input.request.id", "state.session", "state.session.token"]);
    expect(capabilityLocalPathSuggestions({
      type: "object",
      properties: { profile: { type: "object", properties: { name: { type: "string" } } } },
    })).toEqual([".", "profile", "profile.name"]);
  });

  it("previews only the selected output source schema", () => {
    const outputSchema = {
      type: "object",
      properties: {
        text: { type: "string" },
        items: { type: "array", items: { type: "string" } },
        audit: { type: "object", properties: { latest: { type: "integer" } } },
      },
    };

    expect(inferredStateSchemaPreview(outputSchema, "text", "state.report")).toEqual({ type: "string" });
    expect(inferredStateSchemaPreview(outputSchema, "audit.latest", "state.audit.latest")).toEqual({ type: "integer" });
    expect(inferredStateSchemaPreview(outputSchema, "items.1", "state.item")).toEqual({ type: "string" });
    expect(inferredStateSchemaPreview(outputSchema, "items.not-an-index", "state.item")).toBeNull();
    expect(inferredStateSchemaPreview(outputSchema, ".", "state.report")).toEqual(outputSchema);
    expect(inferredStateSchemaPreview(outputSchema, "missing", "state.report")).toBeNull();
    expect(inferredStateSchemaPreview(outputSchema, "text", "state")).toBeNull();
  });
});

describe("selected-step binding diagnostics", () => {
  it("maps only structural row paths and leaves unmatched diagnostics shared", () => {
    const stepId = "render/one~x";
    const diagnostics = [
      diagnostic("nodes[2].input[1].target", stepId),
      diagnostic("nodes[2].output[3].target", stepId),
      diagnostic("/steps/render~1one~0x/input/4/path", null),
      diagnostic("/steps/render~1one~0x/output/5/target", stepId),
      diagnostic("bindings[6].target", stepId),
      diagnostic("/steps/render~1one~0x/input", stepId),
      diagnostic("nodes[4].input[7].target", stepId),
      diagnostic("bindings[8].target", null),
      diagnostic("not a row location", stepId),
      diagnostic("/steps/other/input/9/path", stepId),
      diagnostic("/steps/render~1one~0x/input/10/~2path", null),
    ];

    const inputs = bindingDiagnosticsForStep(diagnostics, stepId, "input", 2);
    expect(inputs.rowIssues[1]?.[0]?.path).toBe("nodes[2].input[1].target");
    expect(inputs.rowIssues[4]?.[0]?.path).toBe("/steps/render~1one~0x/input/4/path");
    expect(inputs.rowIssues[7]).toBeUndefined();
    expect(inputs.unmatchedIssues.map((item) => item.path)).toEqual([
      "nodes[2].output[3].target",
      "/steps/render~1one~0x/output/5/target",
      "/steps/render~1one~0x/input",
      "nodes[4].input[7].target",
      "bindings[8].target",
      "not a row location",
      "/steps/other/input/9/path",
      "/steps/render~1one~0x/input/10/~2path",
    ]);

    const outputs = bindingDiagnosticsForStep(diagnostics, stepId, "output", 2);
    expect(outputs.rowIssues[3]?.[0]?.path).toBe("nodes[2].output[3].target");
    expect(outputs.rowIssues[5]?.[0]?.path).toBe("/steps/render~1one~0x/output/5/target");
    expect(outputs.rowIssues[6]?.[0]?.path).toBe("bindings[6].target");
  });

  it("maps a compiled row diagnostic using only the explicit node index", () => {
    const stepId = "render";
    const inputOnly = [diagnostic("nodes[3].input[4].target", stepId)];
    const outputOnly = [diagnostic("nodes[3].output[2].target", stepId)];

    expect(bindingDiagnosticsForStep(inputOnly, stepId, "input", 3).rowIssues[4]?.[0]?.path).toBe(
      "nodes[3].input[4].target",
    );
    expect(bindingDiagnosticsForStep(outputOnly, stepId, "output", 3).rowIssues[2]?.[0]?.path).toBe(
      "nodes[3].output[2].target",
    );
    expect(bindingDiagnosticsForStep(inputOnly, stepId, "input", 2).unmatchedIssues).toEqual(inputOnly);
    expect(bindingDiagnosticsForStep(outputOnly, stepId, "output", 2).unmatchedIssues).toEqual(outputOnly);
    expect(bindingDiagnosticsForStep(inputOnly, stepId, "input", null).unmatchedIssues).toEqual(inputOnly);
  });
});
