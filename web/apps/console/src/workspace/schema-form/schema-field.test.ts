import { describe, expect, it } from "vitest";
import { normalizeSchema, rebaseSchemaField } from "./schema-field.js";

describe("normalizeSchema", () => {
  it("normalizes primitive, multiline, boolean, and enum fields", () => {
    const field = normalizeSchema({
      type: "object",
      properties: {
        name: { type: "string", title: "Display name", description: "Shown to users." },
        notes: { type: "string", format: "textarea" },
        count: { type: "number" },
        retries: { type: "integer" },
        enabled: { type: "boolean", default: true },
        color: { enum: ["red", 2, false, null] },
      },
      required: ["name", "enabled"],
    });

    expect(field.kind).toBe("object");
    expect(field.children.map((child) => [child.key, child.kind, child.required])).toEqual([
      ["name", "string", true],
      ["notes", "string", false],
      ["count", "number", false],
      ["retries", "integer", false],
      ["enabled", "boolean", true],
      ["color", "enum", false],
    ]);
    expect(field.children[0]).toMatchObject({
      path: ["name"],
      title: "Display name",
      description: "Shown to users.",
    });
    expect(field.children[4]).toMatchObject({
      hasDefault: true,
      defaultValue: true,
    });
    expect(field.children[5]?.enumValues).toEqual(["red", 2, false, null]);
  });

  it("normalizes nested objects and arrays with item fields", () => {
    const field = normalizeSchema({
      type: "object",
      properties: {
        profile: {
          type: "object",
          properties: {
            age: { type: "integer" },
          },
          required: ["age"],
        },
        tags: { type: "array", items: { type: "string" } },
      },
    });

    const profile = field.children[0];
    const tags = field.children[1];
    expect(profile?.children[0]).toMatchObject({
      path: ["profile", "age"],
      key: "age",
      required: true,
      kind: "integer",
    });
    expect(tags).toMatchObject({ path: ["tags"], kind: "array" });
    expect(tags?.item).toMatchObject({ path: ["tags", 0], kind: "string" });
  });

  it("preserves an explicit null default", () => {
    const field = normalizeSchema({
      type: "object",
      properties: { value: { type: "string", default: null } },
    });

    expect(field.children[0]).toMatchObject({
      hasDefault: true,
      defaultValue: null,
    });
  });

  it("uses JSON fallback for unconstrained schemas instead of inventing an object", () => {
    const field = normalizeSchema({});

    expect(field).toMatchObject({ kind: "json", path: [], children: [], item: null });
    expect(field.fallbackReason).toBe("The schema is unconstrained; edit JSON directly.");
  });

  it("uses field-local fallback reasons for unsupported unions and references", () => {
    const field = normalizeSchema({
      type: "object",
      properties: {
        choice: { oneOf: [{ type: "string" }, { type: "number" }] },
        reference: { $ref: "#/definitions/Missing" },
      },
    });

    expect(field.children[0]).toMatchObject({
      kind: "json",
      fallbackReason: "The schema uses oneOf, which the native form cannot represent.",
    });
    expect(field.children[1]).toMatchObject({
      kind: "json",
      fallbackReason: "The schema contains an unresolved $ref, which the native form cannot represent.",
    });
  });

  it("recursively rebases nested object and array item paths", () => {
    const field = normalizeSchema({
      type: "object",
      properties: {
        items: {
          type: "array",
          items: {
            type: "object",
            properties: {
              profile: {
                type: "object",
                properties: { name: { type: "string" } },
              },
            },
          },
        },
      },
    });
    const item = field.children[0]?.item;
    expect(item).not.toBeNull();
    if (!item) return;

    const rebased = rebaseSchemaField(item, ["items", 1]);
    expect(rebased.path).toEqual(["items", 1]);
    expect(rebased.children[0]?.path).toEqual(["items", 1, "profile"]);
    expect(rebased.children[0]?.children[0]?.path).toEqual([
      "items",
      1,
      "profile",
      "name",
    ]);
  });
});
