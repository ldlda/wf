import type {
  ArrayExpression,
  JsonValue,
  InputExpression,
  InputPath,
  LiteralExpression,
  ObjectExpression,
  PathExpression,
} from "../domain/draft-workspace-models.js";
import { normalizeSchema, type SchemaField } from "../schema-form/schema-field.js";
import { formatTOMLPath, parseGraphSourcePath, parseTOMLPath } from "../schema-form/schema-paths.js";

export type ExpressionEditorState =
  | { readonly kind: "literal"; readonly value: unknown; readonly touched: boolean }
  | { readonly kind: "path"; readonly path: string; readonly touched: boolean }
  | { readonly kind: "array"; readonly items: ReadonlyArray<ExpressionEditorState> }
  | { readonly kind: "object"; readonly fields: ReadonlyArray<{ readonly name: string; readonly value: ExpressionEditorState }> };

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

const MAX_JSON_DEPTH = 64;
const MAX_EXPRESSION_NODES = 1024;

const isRecord = (value: unknown): value is JsonRecord =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const hasOwn = (value: JsonRecord, key: string): boolean =>
  Object.prototype.hasOwnProperty.call(value, key);

const hasExactKeys = (value: JsonRecord, keys: ReadonlyArray<string>): boolean => {
  const actual = Reflect.ownKeys(value);
  return actual.length === keys.length && keys.every((key) => actual.includes(key));
};

/** Keep editor literals within the same finite JSON subset as canonical bindings. */
export const isJsonValue = (value: unknown): value is JsonValue => {
  const visit = (current: unknown, depth: number): boolean => {
    if (depth > MAX_JSON_DEPTH) return false;
    if (current === null || typeof current === "boolean" || typeof current === "string") return true;
    if (typeof current === "number") return Number.isFinite(current);
    if (Array.isArray(current)) {
      if (Object.getOwnPropertySymbols(current).length > 0) return false;
      if (!Object.keys(current).every((key) => /^(0|[1-9]\d*)$/.test(key))) return false;
      return current.every((item) => visit(item, depth + 1));
    }
    if (!isRecord(current)) return false;
    if (Object.getPrototypeOf(current) !== Object.prototype && Object.getPrototypeOf(current) !== null) return false;
    if (Object.getOwnPropertySymbols(current).length > 0) return false;
    return Object.values(current).every((item) => visit(item, depth + 1));
  };
  return visit(value, 0);
};

const inputPath = (value: unknown): InputPath | null => {
  if (typeof value === "string") return parseGraphSourcePath(value) === null ? null : value;
  if (!isRecord(value) || !hasExactKeys(value, ["root", "parts"])) return null;
  if (value.root !== "input" && value.root !== "state" && value.root !== "context") return null;
  if (!Array.isArray(value.parts) || !value.parts.every((part): part is string => typeof part === "string")) return null;
  const path = formatTOMLPath([value.root, ...value.parts]);
  return parseGraphSourcePath(path) === null ? null : { root: value.root, parts: [...value.parts] };
};

const parseExpression = (value: unknown, depth: number, nodes: { count: number }): InputExpression | null => {
  if (depth > MAX_JSON_DEPTH || nodes.count >= MAX_EXPRESSION_NODES || !isRecord(value)) return null;
  nodes.count += 1;
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
      const parsed = parseExpression(item, depth + 1, nodes);
      if (parsed === null) return null;
      items.push(parsed);
    }
    return { kind: "array", items } satisfies ArrayExpression;
  }
  if (value.kind === "object" && hasExactKeys(value, ["kind", "fields"]) && isRecord(value.fields)) {
    const fields: Record<string, InputExpression> = {};
    for (const [name, item] of Object.entries(value.fields)) {
      const parsed = parseExpression(item, depth + 1, nodes);
      if (parsed === null) return null;
      Object.defineProperty(fields, name, { configurable: true, enumerable: true, value: parsed, writable: true });
    }
    return { kind: "object", fields } satisfies ObjectExpression;
  }
  return null;
};

/** Parse an external expression before projecting it, without inventing defaults. */
export const parseInputExpression = (value: unknown): InputExpression | null =>
  parseExpression(value, 0, { count: 0 });

const pathText = (path: InputPath): string =>
  typeof path === "string" ? path : formatTOMLPath([path.root, ...path.parts]);

const unsupported = (raw: InputExpression, reason: string): ExpressionProjection => ({
  kind: "unsupported",
  raw,
  reason,
});

const schemaReason = (field: SchemaField | null): string | null => {
  if (field?.fallbackReason === null || field?.fallbackReason === undefined) return null;
  if (field.fallbackReason === "The schema is unconstrained; edit JSON directly.") return null;
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
  return project(parsed, normalizeSchema(schema));
};

const copyStateToExpression = (
  state: ExpressionEditorState,
  depth: number,
  nodes: { count: number },
): InputExpression | null => {
  if (depth > MAX_JSON_DEPTH || nodes.count >= MAX_EXPRESSION_NODES) return null;
  nodes.count += 1;
  switch (state.kind) {
    case "literal":
      return isJsonValue(state.value) ? { kind: "literal", value: state.value } : null;
    case "path":
      return parseGraphSourcePath(state.path) === null ? null : { kind: "path", path: state.path };
    case "array": {
      const items: InputExpression[] = [];
      for (const item of state.items) {
        const expression = copyStateToExpression(item, depth + 1, nodes);
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
        const expression = copyStateToExpression(field.value, depth + 1, nodes);
        if (expression === null) return null;
        Object.defineProperty(fields, field.name, { configurable: true, enumerable: true, value: expression, writable: true });
      }
      return { kind: "object", fields };
    }
  }
};

export const serializeExpressionEditorState = (
  state: ExpressionEditorState,
): InputExpression | null => copyStateToExpression(state, 0, { count: 0 });

const issue = (path: ReadonlyArray<string | number>, message: string): ExpressionValidationIssue => ({ path, message });

const unconstrained = (field: SchemaField | null): boolean =>
  field === null || field.fallbackReason === "The schema is unconstrained; edit JSON directly.";

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
    const required = new Set(field.children.filter((child) => child.required).map((child) => child.key));
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
      }
      if (field?.kind === "object") {
        const required = field.children.filter((child) => child.required).map((child) => child.key);
        for (const name of required) if (!seen.has(name)) issues.push(issue([...path, name], "Required property is missing."));
        for (const entry of state.fields) {
          const child = fieldForObjectName(field, entry.name);
          if (child === null && field.additionalPropertiesKind === "forbidden") issues.push(issue([...path, entry.name], "Additional properties are not allowed."));
          else issues.push(...validateState(entry.value, child, [...path, entry.name]));
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
  const issues = validateState(state, normalizeSchema(schema), []);
  return { valid: issues.length === 0, issues };
};
