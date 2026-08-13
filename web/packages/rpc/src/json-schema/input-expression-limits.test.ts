import { describe, expect, it } from "vitest";
import {
  hasBoundedInputExpressionLiteralValue,
  hasBoundedInputExpressionNodeBudget,
  MAX_INPUT_EXPRESSION_DEPTH,
  MAX_INPUT_EXPRESSION_NODES,
} from "./input-expression-limits.js";

const nestedExpression = (arrayDepth: number): unknown => {
  let expression: unknown = { kind: "literal", value: "leaf" };
  for (let depth = 0; depth < arrayDepth; depth += 1) {
    expression = { kind: "array", items: [expression] };
  }
  return expression;
};

describe("input expression limits", () => {
  it("uses the Python root-at-depth-one boundary", () => {
    expect(hasBoundedInputExpressionNodeBudget(nestedExpression(MAX_INPUT_EXPRESSION_DEPTH - 1))).toBe(true);
    expect(hasBoundedInputExpressionNodeBudget(nestedExpression(MAX_INPUT_EXPRESSION_DEPTH))).toBe(false);
  });

  it("counts literal array and object containers", () => {
    const expression = (objectCount: number) => ({
      kind: "literal",
      value: { items: Array.from({ length: objectCount }, () => ({})) },
    });

    expect(hasBoundedInputExpressionNodeBudget(expression(MAX_INPUT_EXPRESSION_NODES - 3))).toBe(true);
    expect(hasBoundedInputExpressionNodeBudget(expression(MAX_INPUT_EXPRESSION_NODES - 2))).toBe(false);
  });

  it("counts literal container depth from the expression root", () => {
    const nestedLiteral = (containerDepth: number): unknown => {
      let value: unknown = "leaf";
      for (let depth = 0; depth < containerDepth; depth += 1) value = { nested: value };
      return { kind: "literal", value };
    };

    expect(hasBoundedInputExpressionNodeBudget(nestedLiteral(MAX_INPUT_EXPRESSION_DEPTH - 1))).toBe(true);
    expect(hasBoundedInputExpressionNodeBudget(nestedLiteral(MAX_INPUT_EXPRESSION_DEPTH))).toBe(false);
  });

  it("rejects sparse arrays instead of skipping holes", () => {
    const sparse = [] as unknown[];
    sparse.length = 1;
    expect(hasBoundedInputExpressionNodeBudget({ kind: "literal", value: sparse })).toBe(false);
  });

  it("shares strict literal JSON semantics with literal expressions", () => {
    const nestedLiteralValue = (containerDepth: number): unknown => {
      let value: unknown = "leaf";
      for (let depth = 0; depth < containerDepth; depth += 1) value = { nested: value };
      return value;
    };

    expect(hasBoundedInputExpressionLiteralValue(nestedLiteralValue(MAX_INPUT_EXPRESSION_DEPTH - 1))).toBe(true);
    expect(hasBoundedInputExpressionLiteralValue(nestedLiteralValue(MAX_INPUT_EXPRESSION_DEPTH))).toBe(false);

    const values: ReadonlyArray<unknown> = [null, false, "text", 3.14, ["item"], { key: "value" }, Number.NaN, Infinity];
    for (const value of values) {
      expect(hasBoundedInputExpressionLiteralValue(value)).toBe(
        hasBoundedInputExpressionNodeBudget({ kind: "literal", value }),
      );
    }
  });
});
