import { describe, expect, it } from "vitest";
import { resolveLocalSchemaNode } from "./schema-reference.js";

describe("resolveLocalSchemaNode", () => {
  it("resolves direct and nested local definitions", () => {
    const root = {
      $defs: {
        Resource: {
          type: "object",
          properties: {
            logical_source: { type: "string" },
            uri: { type: "string" },
          },
          required: ["logical_source", "uri"],
        },
        Envelope: {
          type: "object",
          properties: { resource: { $ref: "#/$defs/Resource" } },
        },
      },
      properties: { ref: { $ref: "#/$defs/Envelope" } },
    };

    expect(resolveLocalSchemaNode(root, root.properties.ref)).toEqual({
      ok: true,
      schema: {
        type: "object",
        properties: { resource: { $ref: "#/$defs/Resource" } },
      },
    });
    expect(
      resolveLocalSchemaNode(root, root.$defs.Envelope.properties.resource),
    ).toEqual({
      ok: true,
      schema: {
        type: "object",
        properties: {
          logical_source: { type: "string" },
          uri: { type: "string" },
        },
        required: ["logical_source", "uri"],
      },
    });
  });

  it("resolves legacy definitions and escaped JSON Pointer tokens", () => {
    const root = {
      definitions: {
        "name/with~token": { type: "string" },
      },
    };

    expect(
      resolveLocalSchemaNode(root, { $ref: "#/definitions/name~1with~0token" }),
    ).toEqual({
      ok: true,
      schema: { type: "string" },
    });
  });

  it("traverses only own non-negative array indices", () => {
    const root = { items: [{ type: "string" }, { type: "number" }] };

    expect(resolveLocalSchemaNode(root, { $ref: "#/items/1" })).toEqual({
      ok: true,
      schema: { type: "number" },
    });
    expect(resolveLocalSchemaNode(root, { $ref: "#/items/-1" })).toEqual({
      ok: false,
      reason: "Malformed local schema reference pointer.",
    });
  });

  it("merges only annotation siblings over a resolved schema", () => {
    const root = {
      $defs: { Value: { type: "string", title: "Original", default: "old" } },
    };

    expect(
      resolveLocalSchemaNode(root, {
        $ref: "#/$defs/Value",
        title: "Display value",
        description: "Shown to the operator.",
        default: "new",
      }),
    ).toEqual({
      ok: true,
      schema: {
        type: "string",
        title: "Display value",
        description: "Shown to the operator.",
        default: "new",
      },
    });
  });

  it("returns stable failures for unsupported references and malformed pointers", () => {
    const root = { $defs: {} };

    expect(
      resolveLocalSchemaNode(root, { $ref: "https://example.test/schema" }),
    ).toEqual({
      ok: false,
      reason: "External schema references are not supported.",
    });
    expect(resolveLocalSchemaNode(root, { $ref: "other.json#/schema" })).toEqual({
      ok: false,
      reason: "External schema references are not supported.",
    });
    expect(resolveLocalSchemaNode(root, { $ref: "#/missing" })).toEqual({
      ok: false,
      reason: "Local schema reference target was not found.",
    });
    expect(resolveLocalSchemaNode(root, { $ref: "#/$defs/name~2" })).toEqual({
      ok: false,
      reason: "Malformed local schema reference pointer.",
    });
  });

  it("rejects cycles and structural siblings without mutating the schema", () => {
    const root = {
      $defs: {
        First: { $ref: "#/$defs/Second" },
        Second: { $ref: "#/$defs/First" },
        Value: { type: "string" },
      },
    };
    const structuralSibling = { $ref: "#/$defs/Value", properties: {} };

    expect(resolveLocalSchemaNode(root, root.$defs.First)).toEqual({
      ok: false,
      reason: "Local schema reference cycle detected.",
    });
    expect(resolveLocalSchemaNode(root, structuralSibling)).toEqual({
      ok: false,
      reason: "Structural siblings beside $ref are not supported.",
    });
    expect(structuralSibling).toEqual({
      $ref: "#/$defs/Value",
      properties: {},
    });
  });
});
