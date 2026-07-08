import { describe, expect, it } from "vitest";
import { buildSchemaApprovalModel } from "./schema-approval-model.js";

describe("buildSchemaApprovalModel", () => {
  it("projects explicit object schema properties into approval fields", () => {
    const model = buildSchemaApprovalModel({
      schema: {
        type: "object",
        required: ["selected_issue_ids"],
        properties: {
          selected_issue_ids: {
            type: "array",
            description: "Issue ids to create",
            items: { type: "string" },
          },
          comment: { type: "string" },
          approved: { type: "boolean" },
        },
      },
      payload: {
        selected_issue_ids: ["risk-1"],
        comment: "Create the selected issue.",
        approved: true,
      },
      outcomes: ["submitted", "cancelled"],
    });

    expect(model.hasExplicitFields).toBe(true);
    expect(model.outcomes).toEqual(["submitted", "cancelled"]);
    expect(model.fields).toEqual([
      {
        name: "selected_issue_ids",
        label: "selected issue ids",
        kind: "array",
        required: true,
        description: "Issue ids to create",
        valuePreview: "[\"risk-1\"]",
      },
      {
        name: "comment",
        label: "comment",
        kind: "string",
        required: false,
        description: null,
        valuePreview: "Create the selected issue.",
      },
      {
        name: "approved",
        label: "approved",
        kind: "boolean",
        required: false,
        description: null,
        valuePreview: "true",
      },
    ]);
  });

  it("uses payload preview when schema is a loose object without properties", () => {
    const model = buildSchemaApprovalModel({
      schema: { type: "object" },
      payload: {
        selected_issue_ids: ["risk-1"],
        comment: "Create the selected issue.",
      },
      outcomes: ["submitted", "cancelled"],
    });

    expect(model.hasExplicitFields).toBe(false);
    expect(model.fields).toEqual([]);
    expect(model.payloadPreview).toEqual([
      { key: "selected_issue_ids", value: "[\"risk-1\"]" },
      { key: "comment", value: "Create the selected issue." },
    ]);
  });

  it("handles non-object schema without throwing", () => {
    const model = buildSchemaApprovalModel({
      schema: true,
      payload: null,
      outcomes: [],
    });

    expect(model.hasExplicitFields).toBe(false);
    expect(model.fields).toEqual([]);
    expect(model.payloadPreview).toEqual([]);
  });
});
