import type { FieldSource, SchemaField } from "./schema-field.js";

export type FieldSources = Readonly<Record<string, FieldSource>>;

export type SchemaValueIssue = {
  readonly path: ReadonlyArray<string | number>;
  readonly message: string;
};

export type SchemaBinding = {
  readonly target: string;
  readonly path: string;
};

export type SchemaSerializationResult = {
  readonly value: unknown;
  readonly bindings: ReadonlyArray<SchemaBinding>;
  readonly issues: ReadonlyArray<SchemaValueIssue>;
};

type ValueRecord = Record<string, unknown>;

type SerializedField = {
  readonly present: boolean;
  readonly value: unknown;
  readonly bindings: ReadonlyArray<SchemaBinding>;
  readonly issues: ReadonlyArray<SchemaValueIssue>;
};

const isRecord = (value: unknown): value is ValueRecord =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const pathKey = (path: ReadonlyArray<string | number>): string =>
  path.length === 0 ? "root" : path.map(String).join(".");

const targetPath = (path: ReadonlyArray<string | number>): string => path.map(String).join(".");

const hasDescendantSource = (field: SchemaField, sources: FieldSources): boolean => {
  const prefix = targetPath(field.path);
  return Object.keys(sources).some((key) => key.startsWith(`${prefix}.`));
};

const isEmptyValue = (value: unknown): boolean =>
  value === undefined ||
  value === "" ||
  (Array.isArray(value) && value.length === 0) ||
  (isRecord(value) && Object.keys(value).length === 0);

const validBindingPath = (value: string): boolean => {
  const parts = value.split(".");
  return (
    parts.length > 0 &&
    (parts[0] === "input" || parts[0] === "state" || parts[0] === "context") &&
    parts.every((part) => /^[A-Za-z0-9_-]+$/.test(part))
  );
};

const issue = (
  path: ReadonlyArray<string | number>,
  message: string,
): SchemaValueIssue => ({ path, message });

const parseNumber = (
  raw: unknown,
  integer: boolean,
): { readonly value: unknown; readonly message: string | null } => {
  if (typeof raw === "number") {
    return Number.isFinite(raw) && (!integer || Number.isInteger(raw))
      ? { value: raw, message: null }
      : { value: raw, message: integer ? "Enter a whole number." : "Enter a number." };
  }
  if (typeof raw !== "string" || raw.trim() === "") {
    return { value: raw, message: integer ? "Enter a whole number." : "Enter a number." };
  }
  const value = Number(raw);
  return Number.isFinite(value) && (!integer || Number.isInteger(value))
    ? { value, message: null }
    : { value: raw, message: integer ? "Enter a whole number." : "Enter a number." };
};

const parseBoolean = (
  raw: unknown,
): { readonly value: unknown; readonly message: string | null } => {
  if (typeof raw === "boolean") return { value: raw, message: null };
  if (raw === "true") return { value: true, message: null };
  if (raw === "false") return { value: false, message: null };
  return { value: raw, message: "Choose true or false." };
};

const parseEnum = (
  raw: unknown,
  values: ReadonlyArray<string | number | boolean | null>,
): { readonly value: unknown; readonly message: string | null } => {
  const match = values.find((candidate) =>
    candidate === raw ||
    (typeof raw === "string" &&
      (raw === String(candidate) || raw === JSON.stringify(candidate))),
  );
  return match !== undefined || values.some((candidate) => candidate === null && raw === "null")
    ? { value: match === undefined ? null : match, message: null }
    : { value: raw, message: "Choose one of the listed values." };
};

const parseJson = (
  raw: unknown,
): { readonly value: unknown; readonly message: string | null } => {
  if (typeof raw !== "string") return { value: raw, message: null };
  try {
    const value: unknown = JSON.parse(raw);
    return { value, message: null };
  } catch {
    return { value: raw, message: "Enter valid JSON." };
  }
};

const serializeField = (
  field: SchemaField,
  rawValue: unknown,
  sources: FieldSources,
): SerializedField => {
  const source = sources[pathKey(field.path)];
  if (source?.mode === "bind") {
    if (!validBindingPath(source.sourcePath)) {
      return {
        present: field.required,
        value: undefined,
        bindings: [],
        issues: [issue(field.path, "Binding path must start with input, state, or context.")],
      };
    }
    return {
      present: true,
      value: undefined,
      bindings: [{ target: targetPath(field.path), path: source.sourcePath }],
      issues: [],
    };
  }

  const usingDefault = rawValue === undefined && field.hasDefault;
  const sourceValue = source?.mode === "literal" ? source.value : usingDefault ? field.defaultValue : rawValue;
  const hasNestedSource = hasDescendantSource(field, sources);
  // Traverse an omitted container when a descendant is bound; otherwise the binding would disappear.
  const raw =
    sourceValue === undefined && hasNestedSource
      ? field.kind === "array"
        ? []
        : field.kind === "object"
          ? {}
          : sourceValue
      : sourceValue;
  if (!usingDefault && raw === undefined && !field.required && !hasNestedSource) {
    return { present: false, value: undefined, bindings: [], issues: [] };
  }
  if (
    !usingDefault &&
    field.kind !== "object" &&
    field.kind !== "array" &&
    isEmptyValue(raw) &&
    !field.required
  ) {
    return { present: false, value: undefined, bindings: [], issues: [] };
  }

  if (field.kind === "object") {
    if (!isRecord(raw)) {
      return {
        present: field.required,
        value: raw,
        bindings: [],
        issues: [issue(field.path, "Enter an object value.")],
      };
    }
    const value: ValueRecord = {};
    const bindings: SchemaBinding[] = [];
    const issues: SchemaValueIssue[] = [];
    for (const child of field.children) {
      const childValue = serializeField(child, raw[child.key], sources);
      if (childValue.present) value[child.key] = childValue.value;
      bindings.push(...childValue.bindings);
      issues.push(...childValue.issues);
    }
    if (Object.keys(value).length === 0 && !field.required && bindings.length === 0) {
      return { present: false, value: undefined, bindings, issues };
    }
    return { present: true, value, bindings, issues };
  }

  if (field.kind === "array") {
    if (!Array.isArray(raw)) {
      return {
        present: field.required,
        value: raw,
        bindings: [],
        issues: [issue(field.path, "Enter an array value.")],
      };
    }
    const value: unknown[] = [];
    const bindings: SchemaBinding[] = [];
    const issues: SchemaValueIssue[] = [];
    const item = field.item;
    if (item) {
      raw.forEach((itemValue, index) => {
        const itemField: SchemaField = { ...item, path: [...field.path, index] };
        const serialized = serializeField(itemField, itemValue, sources);
        if (serialized.present) value.push(serialized.value);
        bindings.push(...serialized.bindings);
        issues.push(...serialized.issues);
      });
    }
    if (value.length === 0 && bindings.length === 0 && !field.required && !usingDefault) {
      return { present: false, value: undefined, bindings, issues };
    }
    return { present: true, value, bindings, issues };
  }

  if (field.kind === "string") {
    return {
      present: true,
      value: raw,
      bindings: [],
      issues: field.required && raw === "" ? [issue(field.path, "Required field is incomplete.")] : [],
    };
  }

  const parsed =
    field.kind === "number"
      ? parseNumber(raw, false)
      : field.kind === "integer"
        ? parseNumber(raw, true)
        : field.kind === "boolean"
          ? parseBoolean(raw)
          : field.kind === "enum"
            ? parseEnum(raw, field.enumValues)
            : parseJson(raw);
  return {
    present: true,
    value: parsed.value,
    bindings: [],
    issues: parsed.message ? [issue(field.path, parsed.message)] : [],
  };
};

export const serializeSchemaValues = (
  field: SchemaField,
  values: unknown,
  sources: FieldSources = {},
): SchemaSerializationResult => {
  const serialized = serializeField(field, values, sources);
  return {
    value: serialized.value,
    bindings: serialized.bindings,
    issues: serialized.issues,
  };
};

export type { FieldSource } from "./schema-field.js";
