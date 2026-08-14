import type {
  ArrayExpression,
  JsonValue,
  InputExpression,
  InputPath,
  LiteralExpression,
  ObjectExpression,
  PathExpression,
} from "../domain/draft-workspace-models.js";
import {
  hasBoundedInputExpressionLiteralValue,
  hasBoundedInputExpressionNodeBudget,
} from "@lda/workflow-rpc/input-expression-limits";
import {
  normalizeSchema,
  UNCONSTRAINED_SCHEMA_REASON,
  type SchemaField,
} from "../schema-form/schema-field.js";
import { formatTOMLPath, parseGraphSourcePath, parseTOMLPath } from "../schema-form/schema-paths.js";

export type ExpressionEditorState =
  | { readonly kind: "literal"; readonly value: unknown; readonly touched: boolean }
  | { readonly kind: "path"; readonly path: string; readonly touched: boolean }
  | { readonly kind: "array"; readonly items: ReadonlyArray<ExpressionEditorState> }
  | { readonly kind: "object"; readonly fields: ReadonlyArray<{ readonly name: string; readonly value: ExpressionEditorState }> };

const defaultLiteralValue = (field: SchemaField | null): unknown => {
  if (field?.hasDefault) return field.defaultValue;
  if (field?.kind === "boolean") return false;
  if (field?.kind === "number" || field?.kind === "integer") return 0;
  if (field?.kind === "enum") return field.enumValues[0] ?? null;
  return "";
};

export const defaultExpressionEditorState = (
  field: SchemaField | null,
): ExpressionEditorState => {
  if (field?.kind === "array") return { kind: "array", items: [] };
  if (field?.kind === "object") {
    return {
      kind: "object",
      fields: field.children.map((child) => ({
        name: child.key,
        value: defaultExpressionEditorState(child),
      })),
    };
  }
  return { kind: "literal", value: defaultLiteralValue(field), touched: false };
};

export type ExpressionProjection =
  | { readonly kind: "editable"; readonly state: ExpressionEditorState }
  | { readonly kind: "unsupported"; readonly raw: InputExpression; readonly reason: string };

export type ExpressionValidationIssue = {
  readonly path: ReadonlyArray<string | number>;
  readonly message: string;
};

export type ExpressionValidation = {
  readonly valid: boolean;
  readonly issues: ReadonlyArray<ExpressionValidationIssue>;
};

type JsonRecord = Record<string, unknown>;

const isRecord = (value: unknown): value is JsonRecord =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const isNormalizedSchemaField = (value: unknown): value is SchemaField =>
  isRecord(value) &&
  Array.isArray(value.path) &&
  typeof value.kind === "string" &&
  Array.isArray(value.children) &&
  Object.prototype.hasOwnProperty.call(value, "fallbackReason");

const hasOwn = (value: JsonRecord, key: string): boolean =>
  Object.prototype.hasOwnProperty.call(value, key);

const hasExactKeys = (value: JsonRecord, keys: ReadonlyArray<string>): boolean => {
  const actual = Reflect.ownKeys(value);
  const expected = new Set(keys);
  return actual.length === expected.size && actual.every((key) => typeof key === "string" && expected.has(key));
};

/** Keep editor literals within the same finite JSON subset as canonical bindings. */
export const isJsonValue = (value: unknown): value is JsonValue =>
  hasBoundedInputExpressionLiteralValue(value);

const inputPath = (value: unknown): InputPath | null => {
  if (typeof value === "string") return parseGraphSourcePath(value) === null ? null : value;
  if (!isRecord(value) || !hasExactKeys(value, ["root", "parts"])) return null;
  if (value.root !== "input" && value.root !== "state" && value.root !== "context") return null;
  if (!Array.isArray(value.parts) || !value.parts.every((part): part is string => typeof part === "string")) return null;
  const path = formatTOMLPath([value.root, ...value.parts]);
  return parseGraphSourcePath(path) === null ? null : { root: value.root, parts: [...value.parts] };
};

const parseExpression = (value: unknown): InputExpression | null => {
  if (!isRecord(value)) return null;
  if (value.kind === "literal" && hasExactKeys(value, ["kind", "value"]) && isJsonValue(value.value)) {
    return { kind: "literal", value: value.value } satisfies LiteralExpression;
  }
  if (value.kind === "path" && hasExactKeys(value, ["kind", "path"])) {
    const path = inputPath(value.path);
    return path === null ? null : { kind: "path", path } satisfies PathExpression;
  }
  if (value.kind === "array" && hasExactKeys(value, ["kind", "items"]) && Array.isArray(value.items)) {
    const items: InputExpression[] = [];
    for (const item of value.items) {
      const parsed = parseExpression(item);
      if (parsed === null) return null;
      items.push(parsed);
    }
    return { kind: "array", items } satisfies ArrayExpression;
  }
  if (value.kind === "object" && hasExactKeys(value, ["kind", "fields"]) && isRecord(value.fields)) {
    const fields: Record<string, InputExpression> = {};
    for (const [name, item] of Object.entries(value.fields)) {
      const parsed = parseExpression(item);
      if (parsed === null) return null;
      Object.defineProperty(fields, name, { configurable: true, enumerable: true, value: parsed, writable: true });
    }
    return { kind: "object", fields } satisfies ObjectExpression;
  }
  return null;
};

/** Parse an external expression before projecting it, without inventing defaults. */
export const parseInputExpression = (value: unknown): InputExpression | null =>
  hasBoundedInputExpressionNodeBudget(value) ? parseExpression(value) : null;

const pathText = (path: InputPath): string =>
  typeof path === "string" ? path : formatTOMLPath([path.root, ...path.parts]);

const unsupported = (raw: InputExpression, reason: string): ExpressionProjection => ({
  kind: "unsupported",
  raw,
  reason,
});

const schemaReason = (field: SchemaField | null): string | null => {
  if (field?.fallbackReason === null || field?.fallbackReason === undefined) return null;
  if (field.fallbackReason === UNCONSTRAINED_SCHEMA_REASON) return null;
  return field.fallbackReason;
};

const fieldForObjectName = (field: SchemaField, name: string): SchemaField | null => {
  const declared = field.children.find((child) => child.key === name);
  if (declared !== undefined) return declared;
  if (field.additionalPropertiesKind === "schema") return field.additionalProperty;
  return null;
};

const project = (
  raw: InputExpression,
  field: SchemaField | null,
): ExpressionProjection => {
  const reason = schemaReason(field);
  if (reason !== null) return unsupported(raw, reason);
  switch (raw.kind) {
    case "literal":
      return { kind: "editable", state: { kind: "literal", value: raw.value, touched: false } };
    case "path":
      return { kind: "editable", state: { kind: "path", path: pathText(raw.path), touched: false } };
    case "array": {
      if (field !== null && !unconstrained(field) && field.kind !== "array") return unsupported(raw, "The expression is an array but the target schema is not an array.");
      const itemField = field?.item ?? null;
      const items: ExpressionEditorState[] = [];
      for (const item of raw.items) {
        const projected = project(item, itemField);
        if (projected.kind === "unsupported") return projected;
        items.push(projected.state);
      }
      return { kind: "editable", state: { kind: "array", items } };
    }
    case "object": {
      if (field !== null && !unconstrained(field) && field.kind !== "object") return unsupported(raw, "The expression is an object but the target schema is not an object.");
      const fields: Array<{ readonly name: string; readonly value: ExpressionEditorState }> = [];
      for (const [name, item] of Object.entries(raw.fields)) {
        if (field !== null && field.kind === "object" && fieldForObjectName(field, name) === null && field.additionalPropertiesKind === "forbidden") {
          return unsupported(raw, `The schema does not allow additional property ${name}.`);
        }
        const projected = project(item, field?.kind === "object" ? fieldForObjectName(field, name) : null);
        if (projected.kind === "unsupported") return projected;
        fields.push({ name, value: projected.state });
      }
      return { kind: "editable", state: { kind: "object", fields } };
    }
  }
};

export const projectExpressionEditorState = (
  expression: InputExpression,
  schema: unknown,
): ExpressionProjection => {
  const parsed = parseInputExpression(expression);
  if (parsed === null) return unsupported(expression, "The stored expression is malformed or exceeds editor limits.");
  return project(parsed, isNormalizedSchemaField(schema) ? schema : normalizeSchema(schema));
};

const copyStateToExpression = (state: ExpressionEditorState): InputExpression | null => {
  switch (state.kind) {
    case "literal":
      return isJsonValue(state.value) ? { kind: "literal", value: state.value } : null;
    case "path":
      if (parseGraphSourcePath(state.path) === null) return null;
      return { kind: "path", path: state.path };
    case "array": {
      const items: InputExpression[] = [];
      for (const item of state.items) {
        const expression = copyStateToExpression(item);
        if (expression === null) return null;
        items.push(expression);
      }
      return { kind: "array", items };
    }
    case "object": {
      const fields: Record<string, InputExpression> = {};
      const names = new Set<string>();
      for (const field of state.fields) {
        if (names.has(field.name) || field.name.length === 0) return null;
        names.add(field.name);
        const expression = copyStateToExpression(field.value);
        if (expression === null) return null;
        Object.defineProperty(fields, field.name, { configurable: true, enumerable: true, value: expression, writable: true });
      }
      return { kind: "object", fields };
    }
  }
};

export const serializeExpressionEditorState = (
  state: ExpressionEditorState,
): InputExpression | null => {
  const expression = copyStateToExpression(state);
  return expression !== null && hasBoundedInputExpressionNodeBudget(expression) ? expression : null;
};

const issue = (path: ReadonlyArray<string | number>, message: string): ExpressionValidationIssue => ({ path, message });

const unconstrained = (field: SchemaField | null): boolean =>
  field === null || field.fallbackReason === UNCONSTRAINED_SCHEMA_REASON;

const literalIssues = (
  value: unknown,
  field: SchemaField | null,
  path: ReadonlyArray<string | number>,
): ReadonlyArray<ExpressionValidationIssue> => {
  if (!isJsonValue(value)) return [issue(path, "Literal value must be finite JSON.")];
  if (unconstrained(field)) return [];
  if (field === null || field.fallbackReason !== null) return [issue(path, field?.fallbackReason ?? "The target schema is unsupported.")];
  if (field.enumValues.length > 0 && !field.enumValues.some((candidate) => Object.is(candidate, value))) return [issue(path, "Literal value is not one of the allowed enum values.")];
  if (field.kind === "string" && typeof value !== "string") return [issue(path, "Expected a string literal.")];
  if (field.kind === "number" && (typeof value !== "number" || !Number.isFinite(value))) return [issue(path, "Expected a number literal.")];
  if (field.kind === "integer" && (typeof value !== "number" || !Number.isInteger(value))) return [issue(path, "Expected an integer literal.")];
  if (field.kind === "boolean" && typeof value !== "boolean") return [issue(path, "Expected a boolean literal.")];
  if (field.kind === "array") {
    if (!Array.isArray(value)) return [issue(path, "Expected an array literal.")];
    const issues: ExpressionValidationIssue[] = [];
    if (field.minItems !== null && value.length < field.minItems) issues.push(issue(path, `Array must contain at least ${field.minItems} item${field.minItems === 1 ? "" : "s"}.`));
    if (field.maxItems !== null && value.length > field.maxItems) issues.push(issue(path, `Array must contain at most ${field.maxItems} item${field.maxItems === 1 ? "" : "s"}.`));
    value.forEach((item, index) => issues.push(...literalIssues(item, field.item, [...path, index])));
    return issues;
  }
  if (field.kind === "object") {
    if (!isRecord(value)) return [issue(path, "Expected an object literal.")];
    const issues: ExpressionValidationIssue[] = [];
    const required = new Set<string>();
    for (const child of field.children) if (child.required) required.add(child.key);
    for (const name of required) if (!hasOwn(value, name)) issues.push(issue([...path, name], "Required property is missing."));
    for (const [name, item] of Object.entries(value)) {
      const child = fieldForObjectName(field, name);
      if (child === null && field.additionalPropertiesKind === "forbidden") issues.push(issue([...path, name], "Additional properties are not allowed."));
      else issues.push(...literalIssues(item, child, [...path, name]));
    }
    return issues;
  }
  return [];
};

const validateState = (
  state: ExpressionEditorState,
  field: SchemaField | null,
  path: ReadonlyArray<string | number>,
): ReadonlyArray<ExpressionValidationIssue> => {
  const reason = schemaReason(field);
  if (reason !== null) return [issue(path, reason)];
  switch (state.kind) {
    case "literal":
      return literalIssues(state.value, field, path);
    case "path":
      return parseGraphSourcePath(state.path) === null
        ? [issue(path, "Path must start with input., state., or context.")]
        : [];
    case "array": {
      if (field !== null && !unconstrained(field) && field.kind !== "array") return [issue(path, "Construct array requires an array schema.")];
      const issues: ExpressionValidationIssue[] = [];
      if (field?.minItems !== null && field?.minItems !== undefined && state.items.length < field.minItems) issues.push(issue(path, `Array must contain at least ${field.minItems} item${field.minItems === 1 ? "" : "s"}.`));
      if (field?.maxItems !== null && field?.maxItems !== undefined && state.items.length > field.maxItems) issues.push(issue(path, `Array must contain at most ${field.maxItems} item${field.maxItems === 1 ? "" : "s"}.`));
      state.items.forEach((item, index) => issues.push(...validateState(item, field?.item ?? null, [...path, index])));
      return issues;
    }
    case "object": {
      if (field !== null && !unconstrained(field) && field.kind !== "object") return [issue(path, "Construct object requires an object schema.")];
      const issues: ExpressionValidationIssue[] = [];
      const seen = new Set<string>();
      for (const entry of state.fields) {
        if (seen.has(entry.name)) issues.push(issue([...path, entry.name], "Duplicate object field name."));
        seen.add(entry.name);
        if (entry.name.length === 0) issues.push(issue(path, "Object field name is required."));
      }
      if (field?.kind === "object") {
        const required = new Set<string>();
        for (const child of field.children) if (child.required) required.add(child.key);
        for (const name of required) if (!seen.has(name)) issues.push(issue([...path, name], "Required property is missing."));
      }
      for (const entry of state.fields) {
        const child = field?.kind === "object" ? fieldForObjectName(field, entry.name) : null;
        if (field?.kind === "object" && child === null && field.additionalPropertiesKind === "forbidden") {
          issues.push(issue([...path, entry.name], "Additional properties are not allowed."));
        } else {
          issues.push(...validateState(entry.value, child, [...path, entry.name]));
        }
      }
      return issues;
    }
  }
};

export const validateExpressionEditorState = (
  state: ExpressionEditorState,
  schema: unknown,
): ExpressionValidation => {
  const field = isNormalizedSchemaField(schema) ? schema : normalizeSchema(schema);
  const issues = [...validateState(state, field, [])];
  if (issues.length === 0) {
    const expression = copyStateToExpression(state);
    if (expression === null || !hasBoundedInputExpressionNodeBudget(expression)) {
      issues.push(issue([], "Expression exceeds the canonical depth or node budget."));
    }
  }
  return { valid: issues.length === 0, issues };
};
