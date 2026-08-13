import { describe, expect, it } from "vitest";
import type { InputExpression } from "../domain/draft-workspace-models.js";
import {
  isJsonValue,
  parseInputExpression,
  projectExpressionEditorState,
  serializeExpressionEditorState,
  validateExpressionEditorState,
  type ExpressionEditorState,
} from "./input-expression-editor.js";

const concatSchema = {
  type: "object",
  required: ["items", "separator"],
  properties: {
    items: {
      type: "array",
      minItems: 1,
      maxItems: 3,
      items: { type: "string" },
    },
    separator: { type: "string" },
  },
};

const expression: InputExpression = {
  kind: "object",
  fields: {
    separator: { kind: "literal", value: " " },
    items: {
      kind: "array",
      items: [
        { kind: "path", path: { root: "state", parts: ["foo"] } },
        { kind: "literal", value: "wowcool" },
      ],
    },
  },
};

const editable = (state: ExpressionEditorState) => ({ kind: "editable", state }) as const;

describe("input expression editor projection", () => {
  it("round-trips nested arrays and objects while retaining field order and null", () => {
    const canonical: InputExpression = {
      kind: "object",
      fields: {
        z_last: {
          kind: "array",
          items: [
            { kind: "literal", value: null },
            { kind: "object", fields: { nested: { kind: "literal", value: false } } },
          ],
        },
        a_first: { kind: "literal", value: "kept" },
      },
    };

    const projected = projectExpressionEditorState(canonical, {
      type: "object",
      properties: {
        z_last: { type: "array", items: {} },
        a_first: { type: "string" },
      },
    });

    expect(projected).toEqual(editable({
      kind: "object",
      fields: [
        {
          name: "z_last",
          value: {
            kind: "array",
            items: [
              { kind: "literal", value: null, touched: false },
              {
                kind: "object",
                fields: [{ name: "nested", value: { kind: "literal", value: false, touched: false } }],
              },
            ],
          },
        },
        { name: "a_first", value: { kind: "literal", value: "kept", touched: false } },
      ],
    }));

    if (projected.kind !== "editable") throw new Error("expected editable expression");
    expect(serializeExpressionEditorState(projected.state)).toEqual({
      kind: "object",
      fields: {
        z_last: {
          kind: "array",
          items: [
            { kind: "literal", value: null },
            { kind: "object", fields: { nested: { kind: "literal", value: false } } },
          ],
        },
        a_first: { kind: "literal", value: "kept" },
      },
    });
  });

  it("normalizes structural paths through the canonical path formatter", () => {
    const canonical: InputExpression = {
      kind: "array",
      items: [{ kind: "path", path: { root: "context", parts: ["request", "display name"] } }],
    };
    const projected = projectExpressionEditorState(canonical, { type: "array", items: {} });

    expect(projected).toEqual(editable({
      kind: "array",
      items: [{ kind: "path", path: 'context.request."display name"', touched: false }],
    }));
    if (projected.kind !== "editable") throw new Error("expected editable expression");
    expect(serializeExpressionEditorState(projected.state)).toEqual({
      kind: "array",
      items: [{ kind: "path", path: 'context.request."display name"' }],
    });
    expect(serializeExpressionEditorState({ ...projected.state })).toEqual({
      kind: "array",
      items: [{ kind: "path", path: 'context.request."display name"' }],
    });
    expect(projectExpressionEditorState({
      kind: "array",
      items: [{ kind: "path", path: 'context.request."display name"' }],
    }, { type: "array", items: {} })).toEqual(projected);
  });

  it("serializes an edited structural path from its current string", () => {
    const projected = projectExpressionEditorState(
      { kind: "path", path: { root: "state", parts: ["foo"] } },
      {},
    );

    if (projected.kind !== "editable" || projected.state.kind !== "path") {
      throw new Error("expected editable path expression");
    }
    expect(serializeExpressionEditorState({ ...projected.state, path: "state.bar", touched: true })).toEqual({
      kind: "path",
      path: "state.bar",
    });
  });

  it("allows empty and nonempty arrays when item schema is omitted", () => {
    expect(projectExpressionEditorState({ kind: "array", items: [] }, { type: "array" })).toEqual(
      editable({ kind: "array", items: [] }),
    );
    expect(projectExpressionEditorState({
      kind: "array",
      items: [{ kind: "literal", value: "free-form" }],
    }, { type: "array" })).toEqual(editable({
      kind: "array",
      items: [{ kind: "literal", value: "free-form", touched: false }],
    }));
  });

  it("allows empty arrays when no minimum is declared and validates declared bounds", () => {
    const empty = { kind: "array", items: [] } satisfies ExpressionEditorState;
    expect(validateExpressionEditorState(empty, { type: "array", items: { type: "string" } })).toEqual({
      valid: true,
      issues: [],
    });
    expect(validateExpressionEditorState(empty, { type: "array", minItems: 1, items: { type: "string" } })).toMatchObject({
      valid: false,
      issues: [expect.objectContaining({ message: expect.stringMatching(/at least 1/i) })],
    });
    const tooMany = { kind: "array", items: [
      { kind: "literal", value: "a", touched: false },
      { kind: "literal", value: "b", touched: false },
    ] } satisfies ExpressionEditorState;
    expect(validateExpressionEditorState(tooMany, { type: "array", maxItems: 1, items: { type: "string" } })).toMatchObject({
      valid: false,
      issues: [expect.objectContaining({ message: expect.stringMatching(/at most 1/i) })],
    });
  });

  it("validates required fields and additionalProperties without inventing fields", () => {
    const missingRequired = {
      kind: "object",
      fields: [{ name: "optional", value: { kind: "literal", value: "ok", touched: false } }],
    } satisfies ExpressionEditorState;
    expect(validateExpressionEditorState(missingRequired, {
      type: "object",
      required: ["required"],
      properties: { required: { type: "string" }, optional: { type: "string" } },
      additionalProperties: false,
    })).toMatchObject({
      valid: false,
      issues: [expect.objectContaining({ path: ["required"], message: expect.stringMatching(/required/i) })],
    });

    const unknownField = {
      kind: "object",
      fields: [{ name: "extra", value: { kind: "literal", value: "ok", touched: false } }],
    } satisfies ExpressionEditorState;
    expect(validateExpressionEditorState(unknownField, {
      type: "object",
      properties: {},
      additionalProperties: false,
    })).toMatchObject({
      valid: false,
      issues: [expect.objectContaining({ path: ["extra"], message: expect.stringMatching(/additional|not allowed/i) })],
    });
    expect(validateExpressionEditorState(unknownField, {
      type: "object",
      properties: {},
      additionalProperties: { type: "string" },
    })).toEqual({ valid: true, issues: [] });
  });

  it("rejects duplicate fields before serialization", () => {
    expect(serializeExpressionEditorState({
      kind: "object",
      fields: [
        { name: "same", value: { kind: "literal", value: 1, touched: true } },
        { name: "same", value: { kind: "literal", value: 2, touched: true } },
      ],
    })).toBeNull();
  });

  it("returns unsupported with the original expression for ref and composition failures", () => {
    const cases: ReadonlyArray<[string, InputExpression, unknown]> = [
      ["missing ref", { kind: "literal", value: "kept" }, { $ref: "#/$defs/Missing" }],
      ["remote ref", { kind: "literal", value: "kept" }, { $ref: "https://example.test/schema.json" }],
      ["composition", { kind: "literal", value: "kept" }, { oneOf: [{ type: "string" }, { type: "number" }] }],
      ["cycle", { kind: "literal", value: "kept" }, {
        $defs: { Node: { $ref: "#/$defs/Node" } },
        $ref: "#/$defs/Node",
      }],
    ];

    for (const [label, raw, schema] of cases) {
      expect(projectExpressionEditorState(raw, schema), label).toEqual({
        kind: "unsupported",
        raw,
        reason: expect.any(String),
      });
    }
  });

  it("rejects malformed editor leaves instead of substituting an empty literal", () => {
    expect(serializeExpressionEditorState({ kind: "literal", value: undefined, touched: true })).toBeNull();
    expect(serializeExpressionEditorState({ kind: "path", path: "not-a-source", touched: true })).toBeNull();
    expect(validateExpressionEditorState({ kind: "path", path: "not-a-source", touched: true }, concatSchema)).toMatchObject({
      valid: false,
      issues: [expect.objectContaining({ message: expect.stringMatching(/input\., state\., or context/i) })],
    });
  });

  it("validates nested object leaves under unconstrained schemas", () => {
    const state: ExpressionEditorState = {
      kind: "object",
      fields: [{
        name: "nested",
        value: {
          kind: "object",
          fields: [
            { name: "badPath", value: { kind: "path", path: "not-a-source", touched: true } },
            { name: "badLiteral", value: { kind: "literal", value: undefined, touched: true } },
          ],
        },
      }],
    };

    expect(validateExpressionEditorState(state, {})).toMatchObject({
      valid: false,
      issues: [
        expect.objectContaining({ path: ["nested", "badPath"] }),
        expect.objectContaining({ path: ["nested", "badLiteral"] }),
      ],
    });
  });

  it("rejects sparse literal arrays", () => {
    const sparse = [] as unknown[];
    sparse.length = 1;
    expect(isJsonValue(sparse)).toBe(false);
    expect(serializeExpressionEditorState({ kind: "literal", value: sparse, touched: true })).toBeNull();
  });

  it("accepts every browser literal within the canonical literal-expression budget", () => {
    const nestedLiteralValue = (containerDepth: number): unknown => {
      let value: unknown = "leaf";
      for (let depth = 0; depth < containerDepth; depth += 1) value = { nested: value };
      return value;
    };

    const values: ReadonlyArray<unknown> = [
      null,
      false,
      "text",
      3.14,
      ["item"],
      { key: "value" },
      nestedLiteralValue(63),
    ];
    for (const value of values) {
      expect(isJsonValue(value)).toBe(true);
      expect(parseInputExpression({ kind: "literal", value })).not.toBeNull();
    }
    expect(isJsonValue(nestedLiteralValue(64))).toBe(false);
  });

  it("uses the shared budget for parsing, projection, validation, and serialization", () => {
    const oversized = {
      kind: "literal",
      value: { items: Array.from({ length: 1022 }, () => ({})) },
    } as const;

    expect(parseInputExpression(oversized)).toBeNull();
    expect(projectExpressionEditorState(oversized as InputExpression, {})).toMatchObject({
      kind: "unsupported",
      reason: expect.stringMatching(/limits/i),
    });
    expect(serializeExpressionEditorState({ kind: "literal", value: oversized.value, touched: true })).toBeNull();
    expect(validateExpressionEditorState({ kind: "literal", value: oversized.value, touched: true }, {})).toMatchObject({
      valid: false,
      issues: [expect.objectContaining({ message: expect.stringMatching(/finite JSON|budget/i) })],
    });
  });
});
