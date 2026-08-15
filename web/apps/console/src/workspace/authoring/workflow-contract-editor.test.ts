import { describe, expect, it } from "vitest";
import {
  normalizeOutcomes,
  projectWorkflowSchema,
  serializeWorkflowSchema,
} from "./workflow-contract-editor.js";

describe("workflow contract schema projection", () => {
  it("round-trips nested fields while preserving root and unknown metadata", () => {
    const schema = {
      type: "object",
      title: "Input",
      $defs: { Tag: { type: "string" } },
      "x-root": { kept: true },
      required: ["request"],
      properties: {
        request: {
          type: "object",
          description: "Request details",
          "x-field": "keep",
          required: ["title"],
          properties: {
            title: { type: "string" },
            tags: { type: "array", items: { type: "string", minLength: 1 } },
          },
        },
      },
    };
    const projection = projectWorkflowSchema(schema);

    expect(projection.rows[0]).toMatchObject({
      name: "request",
      type: "object",
      required: true,
      description: "Request details",
    });
    expect(projection.rows[0]?.children[1]?.item).toMatchObject({ type: "string" });
    expect(serializeWorkflowSchema(projection, projection.rows)).toEqual(schema);
  });

  it("projects and preserves state defaults and reducer references", () => {
    const schema = {
      type: "object",
      properties: {
        issues: {
          type: "array",
          items: { type: "string" },
          default: [],
          reducer: { capability: "wf.std.append", config: { unique: true } },
        },
      },
    };
    const projection = projectWorkflowSchema(schema);
    expect(projection.rows[0]).toMatchObject({ hasDefault: true, defaultValue: [] });
    expect(serializeWorkflowSchema(projection, projection.rows, { state: true })).toEqual(schema);
  });

  it("keeps unsupported composition intact while another field changes", () => {
    const schema = {
      type: "object",
      properties: {
        choice: { oneOf: [{ type: "string" }, { type: "number" }], "x-note": "keep" },
        title: { type: "string" },
      },
    };
    const projection = projectWorkflowSchema(schema);
    const choice = projection.rows[0];
    expect(choice?.unsupportedReason).toMatch(/oneOf/);
    const rows = projection.rows.map((row) =>
      row.name === "title" ? { ...row, description: "Updated" } : row,
    );
    expect(serializeWorkflowSchema(projection, rows).properties).toEqual({
      choice: schema.properties.choice,
      title: { type: "string", description: "Updated" },
    });
  });

  it("normalizes ordered outcomes without blanks or duplicates", () => {
    expect(normalizeOutcomes(["ok", " ", "cancelled", "ok"])).toEqual(["ok", "cancelled"]);
  });
});
