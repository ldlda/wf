import type { JsonObject } from "../domain/draft-workspace-models.js";

export type WorkflowContractKind = "input" | "state" | "output" | "outcomes";
export type WorkflowSchemaFieldType =
  | "value"
  | "string"
  | "integer"
  | "number"
  | "boolean"
  | "object"
  | "array";

export type WorkflowSchemaFieldRow = {
  readonly id: string;
  readonly name: string;
  readonly type: WorkflowSchemaFieldType;
  readonly required: boolean;
  readonly description: string;
  readonly hasDefault: boolean;
  readonly defaultValue: unknown;
  readonly reducer: unknown;
  readonly children: ReadonlyArray<WorkflowSchemaFieldRow>;
  readonly item: WorkflowSchemaFieldRow | null;
  readonly unsupportedReason: string | null;
  readonly raw: JsonObject;
};

export type WorkflowSchemaProjection = {
  readonly schema: JsonObject;
  readonly rows: ReadonlyArray<WorkflowSchemaFieldRow>;
  readonly rootUnsupportedReason: string | null;
};

export type WorkflowOutputBindingRow = {
  readonly id: string;
  readonly source: string;
  readonly target: string;
  readonly value?: unknown;
};

export type WorkflowContractPatch = {
  readonly inputSchema?: JsonObject;
  readonly stateSchema?: JsonObject;
  readonly outputSchema?: JsonObject;
  readonly outcomes?: ReadonlyArray<string>;
};

type WorkflowSchemaPathSegment =
  | { readonly kind: "property"; readonly name: string }
  | { readonly kind: "array-item" };

const MAX_DEPTH = 64;
const COMPOSITION_KEYS = ["oneOf", "anyOf", "allOf", "not", "if", "then", "else"] as const;

const isRecord = (value: unknown): value is JsonObject =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const schemaFieldId = (path: ReadonlyArray<WorkflowSchemaPathSegment>): string =>
  // JSON-encoded tagged segments keep a property named "a.b" distinct from
  // a nested property path ["a", "b"].
  JSON.stringify(path);

export const copyJson = (value: unknown): unknown => {
  if (Array.isArray(value)) return value.map(copyJson);
  if (!isRecord(value)) return value;
  return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, copyJson(item)]));
};

const copyObject = (value: JsonObject): JsonObject => copyJson(value) as JsonObject;

const unsupportedReason = (schema: JsonObject, depth: number): string | null => {
  if (depth >= MAX_DEPTH) return "Schema editor depth limit exceeded.";
  const composition = COMPOSITION_KEYS.find((key) => Object.hasOwn(schema, key));
  if (composition !== undefined) {
    return `The field uses ${composition}, which the focused editor cannot represent.`;
  }
  if (Object.hasOwn(schema, "$ref")) {
    return "The field uses a reference, which remains available in Advanced details.";
  }
  const type = schema.type;
  if (
    type !== undefined &&
    type !== "string" &&
    type !== "integer" &&
    type !== "number" &&
    type !== "boolean" &&
    type !== "object" &&
    type !== "array"
  ) return "The field type is not supported by the focused editor.";
  return null;
};

const fieldType = (schema: JsonObject): WorkflowSchemaFieldType => {
  const type = schema.type;
  return type === "string" ||
    type === "integer" ||
    type === "number" ||
    type === "boolean" ||
    type === "object" ||
    type === "array"
    ? type
    : "value";
};

const projectField = (
  name: string,
  schema: unknown,
  required: boolean,
  path: ReadonlyArray<WorkflowSchemaPathSegment>,
  depth: number,
): WorkflowSchemaFieldRow => {
  const raw = isRecord(schema) ? copyObject(schema) : {};
  const reason = isRecord(schema)
    ? unsupportedReason(schema, depth)
    : "The field schema is not an object.";
  const type = fieldType(raw);
  const requiredNames = new Set(
    Array.isArray(raw.required)
      ? raw.required.filter((value): value is string => typeof value === "string")
      : [],
  );
  const properties = isRecord(raw.properties) ? raw.properties : {};
  const children = reason === null && type === "object"
    ? Object.entries(properties).map(([childName, childSchema]) =>
        projectField(
          childName,
          childSchema,
          requiredNames.has(childName),
          [...path, { kind: "property", name: childName }],
          depth + 1,
        ),
      )
    : [];
  const item = reason === null && type === "array" && raw.items !== undefined
    ? projectField("item", raw.items, true, [...path, { kind: "array-item" }], depth + 1)
    : null;
  return {
    id: schemaFieldId(path),
    name,
    type,
    required,
    description: typeof raw.description === "string" ? raw.description : "",
    hasDefault: Object.hasOwn(raw, "default"),
    defaultValue: copyJson(raw.default),
    reducer: copyJson(raw.reducer),
    children,
    item,
    unsupportedReason: reason,
    raw,
  };
};

export const projectWorkflowSchema = (schema: unknown): WorkflowSchemaProjection => {
  const root = isRecord(schema) ? copyObject(schema) : { type: "object", properties: {} };
  const rootReason = unsupportedReason(root, 0);
  const requiredNames = new Set(
    Array.isArray(root.required)
      ? root.required.filter((value): value is string => typeof value === "string")
      : [],
  );
  const properties = isRecord(root.properties) ? root.properties : {};
  return {
    schema: root,
    rows: rootReason === null
      ? Object.entries(properties).map(([name, field]) =>
          projectField(
            name,
            field,
            requiredNames.has(name),
            [{ kind: "property", name }],
            1,
          ),
        )
      : [],
    rootUnsupportedReason: rootReason,
  };
};

export const validateWorkflowSchemaRows = (
  rows: ReadonlyArray<WorkflowSchemaFieldRow>,
): ReadonlyArray<string> => {
  const issues = new Set<string>();
  const visit = (scopeRows: ReadonlyArray<WorkflowSchemaFieldRow>): void => {
    const names = new Set<string>();
    for (const row of scopeRows) {
      if (row.name.trim() === "") issues.add("Field names must not be blank.");
      else if (names.has(row.name)) issues.add("Field names must be unique within each object.");
      names.add(row.name);
      visit(row.children);
      if (row.item !== null) visit([row.item]);
    }
  };
  visit(rows);
  return [...issues];
};

const serializeField = (row: WorkflowSchemaFieldRow, state: boolean): JsonObject => {
  if (row.unsupportedReason !== null) return copyObject(row.raw);
  const next = copyObject(row.raw);
  if (row.type === "value") delete next.type;
  else next.type = row.type;
  if (row.description.trim() === "") delete next.description;
  else next.description = row.description;

  if (row.type === "object") {
    next.properties = Object.fromEntries(
      row.children.map((child) => [child.name, serializeField(child, state)]),
    );
    const required = row.children.filter((child) => child.required).map((child) => child.name);
    if (required.length === 0) delete next.required;
    else next.required = required;
  } else {
    delete next.properties;
    delete next.required;
  }
  if (row.type === "array") {
    next.items = row.item === null ? {} : serializeField(row.item, state);
  } else {
    delete next.items;
  }
  if (state) {
    if (row.hasDefault) next.default = copyJson(row.defaultValue);
    else delete next.default;
    if (row.reducer === undefined || row.reducer === null || row.reducer === "") delete next.reducer;
    else next.reducer = copyJson(row.reducer);
  }
  return next;
};

export const serializeWorkflowSchema = (
  projection: WorkflowSchemaProjection,
  rows: ReadonlyArray<WorkflowSchemaFieldRow>,
  options: { readonly state?: boolean } = {},
): JsonObject => {
  if (projection.rootUnsupportedReason !== null) return copyObject(projection.schema);
  const issues = validateWorkflowSchemaRows(rows);
  if (issues.length > 0) throw new Error(issues.join(" "));
  const next = copyObject(projection.schema);
  next.type = "object";
  next.properties = Object.fromEntries(
    rows.map((row) => [row.name, serializeField(row, options.state === true)]),
  );
  const required = rows.filter((row) => row.required).map((row) => row.name);
  if (required.length === 0) delete next.required;
  else next.required = required;
  return next;
};

export const normalizeOutcomes = (values: ReadonlyArray<string>): ReadonlyArray<string> => {
  const seen = new Set<string>();
  const outcomes: string[] = [];
  for (const value of values) {
    const normalized = value.trim();
    if (normalized === "" || seen.has(normalized)) continue;
    seen.add(normalized);
    outcomes.push(normalized);
  }
  return outcomes;
};
