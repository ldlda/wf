import { Either, Schema } from "effect";
import { describe, expect, it } from "vitest";
import {
  translateJsonSchema,
  type JsonSchemaTranslationError,
} from "./translator.js";

const translatedSchema = (
  schema: unknown,
  components: Readonly<Record<string, unknown>> = {},
): Schema.Schema.AnyNoContext => {
  const result = translateJsonSchema(schema, { components });
  if (Either.isLeft(result)) {
    throw new Error(`${result.left.path}: ${result.left.message}`);
  }
  return result.right;
};

const accepts = (schema: Schema.Schema.AnyNoContext, value: unknown): boolean =>
  Either.isRight(
    Schema.decodeUnknownEither(schema)(value, { onExcessProperty: "error" }),
  );

const rejected = (
  schema: unknown,
  components: Readonly<Record<string, unknown>> = {},
): JsonSchemaTranslationError => {
  const result = translateJsonSchema(schema, { components });
  if (Either.isRight(result)) throw new Error("expected translation to fail");
  return result.left;
};

describe("translateJsonSchema", () => {
  it("translates constrained primitives, arrays, and closed objects", () => {
    const schema = translatedSchema({
      additionalProperties: false,
      properties: {
        enabled: { type: "boolean" },
        id: { minLength: 2, pattern: "^w", type: "string" },
        score: { maximum: 10, minimum: 0, type: "integer" },
        tags: {
          items: { enum: ["a", "b"], type: "string" },
          maxItems: 2,
          minItems: 1,
          type: "array",
        },
      },
      required: ["id", "score", "tags"],
      type: "object",
    });

    expect(accepts(schema, { id: "wf", score: 4, tags: ["a"] })).toBe(true);
    expect(accepts(schema, { id: "x", score: 4, tags: ["a"] })).toBe(false);
    expect(accepts(schema, { id: "wf", score: 4.5, tags: ["a"] })).toBe(false);
    expect(accepts(schema, { id: "wf", score: 4, tags: [], extra: true })).toBe(
      false,
    );
  });

  it("supports open and schema-constrained additional properties", () => {
    const open = translatedSchema({
      additionalProperties: true,
      properties: { id: { type: "string" } },
      required: ["id"],
      type: "object",
    });
    const numericRest = translatedSchema({
      additionalProperties: { type: "number" },
      properties: {},
      type: "object",
    });
    const openAny = translatedSchema({
      additionalProperties: true,
      type: "object",
    });

    expect(accepts(open, { id: "x", metadata: { nested: true } })).toBe(true);
    expect(accepts(open, { id: "x", invalid: undefined })).toBe(false);
    expect(accepts(openAny, new Date())).toBe(false);
    expect(accepts(openAny, new Map())).toBe(false);
    expect(accepts(numericRest, { first: 1, second: 2.5 })).toBe(true);
    expect(accepts(numericRest, { first: "1" })).toBe(false);
  });

  it("keeps empty closed objects closed", () => {
    const emptyObject = translatedSchema({
      additionalProperties: false,
      type: "object",
    });

    expect(accepts(emptyObject, {})).toBe(true);
    expect(accepts(emptyObject, [])).toBe(false);
    expect(accepts(emptyObject, { extra: true })).toBe(false);
  });

  it("fails closed on prototype-like JSON property names", () => {
    const error = rejected({
      additionalProperties: false,
      properties: Object.fromEntries([
        ["__proto__", { type: "string" }],
        ["toString", { type: "string" }],
      ]),
      required: ["__proto__", "toString"],
      type: "object",
    });

    expect(error.keyword).toBe("properties");
    expect(error.message).toMatch(/prototype/i);
  });

  it("counts Unicode code points for string length constraints", () => {
    const exactlyOneCharacter = translatedSchema({
      maxLength: 1,
      minLength: 1,
      type: "string",
    });

    expect(accepts(exactlyOneCharacter, "😀")).toBe(true);
    expect(accepts(exactlyOneCharacter, "ab")).toBe(false);
  });

  it("resolves local references and recursive component schemas", () => {
    const components = {
      TreeNode: {
        additionalProperties: false,
        properties: {
          children: {
            items: { $ref: "#/components/schemas/TreeNode" },
            type: "array",
          },
          label: { type: "string" },
        },
        required: ["label", "children"],
        type: "object",
      },
    };
    const schema = translatedSchema(
      {
        anyOf: [
          { $ref: "#/components/schemas/TreeNode" },
          { type: "null" },
        ],
      },
      components,
    );

    expect(
      accepts(schema, {
        children: [{ children: [], label: "child" }],
        label: "root",
      }),
    ).toBe(true);
    expect(accepts(schema, null)).toBe(true);
    expect(accepts(schema, { children: [{ label: "child" }], label: "root" })).toBe(
      false,
    );
  });

  it("rejects unproductive component reference cycles", () => {
    const components = {
      Loop: { $ref: "#/components/schemas/Loop" },
    };

    const error = rejected({ $ref: "#/components/schemas/Loop" }, components);
    expect(error.keyword).toBe("$ref");
    expect(error.message).toMatch(/recursive.*structural boundary/i);
  });

  it("supports productive recursion through a component alias", () => {
    const components = {
      Alias: { $ref: "#/components/schemas/Node" },
      Node: {
        additionalProperties: false,
        properties: {
          child: { $ref: "#/components/schemas/Alias" },
        },
        type: "object",
      },
    };
    const schema = translatedSchema(
      { $ref: "#/components/schemas/Node" },
      components,
    );

    expect(accepts(schema, { child: { child: {} } })).toBe(true);
  });

  it("treats boolean schemas as JSON-only accept-all or reject-all", () => {
    const acceptJson = translatedSchema(true);
    const rejectAll = translatedSchema(false);
    const cyclic: Record<string, unknown> = {};
    cyclic.self = cyclic;

    expect(accepts(acceptJson, { nested: [1, true, null] })).toBe(true);
    expect(accepts(acceptJson, undefined)).toBe(false);
    expect(accepts(acceptJson, new Date())).toBe(false);
    expect(accepts(acceptJson, new Map())).toBe(false);
    expect(accepts(acceptJson, cyclic)).toBe(false);
    expect(accepts(rejectAll, null)).toBe(false);
  });

  it.each([
    [{ oneOf: [{ type: "string" }, { minLength: 1, type: "string" }] }, "oneOf"],
    [
      {
        if: { properties: { kind: { const: "x" } } },
        then: { required: ["value"] },
        type: "object",
      },
      "if",
    ],
    [{ format: "date-time", type: "string" }, "format"],
  ])(
    "rejects unsupported semantics instead of weakening them: %s",
    (schema, keyword) => {
      const error = rejected(schema);
      expect(error.keyword).toBe(keyword);
    },
  );

  it("rejects external and dangling component references", () => {
    expect(rejected({ $ref: "https://example.com/schema.json" }).keyword).toBe(
      "$ref",
    );
    expect(
      rejected({ $ref: "#/components/schemas/Missing" }).message,
    ).toMatch(/missing component/i);
    expect(
      rejected({ $ref: "#/components/schemas/__proto__" }).message,
    ).toMatch(/missing component/i);
  });

  it("rejects const and enum values that contradict their declared type", () => {
    expect(rejected({ const: 1, type: "string" }).keyword).toBe("type");
    expect(rejected({ enum: ["ok", 1], type: "string" }).keyword).toBe("type");
  });

  it("rejects empty or duplicate enum declarations", () => {
    expect(rejected({ enum: [] }).keyword).toBe("enum");
    expect(rejected({ enum: ["same", "same"] }).keyword).toBe("enum");
  });

  it("fails closed on required names supplied only by additionalProperties", () => {
    const error = rejected({
      additionalProperties: { type: "string" },
      required: ["dynamic"],
      type: "object",
    });

    expect(error.keyword).toBe("required");
    expect(error.message).toMatch(/not supported/i);
  });
});
