export type SchemaApprovalFieldKind = "string" | "number" | "boolean" | "array" | "object" | "unknown";

export type SchemaApprovalField = {
  readonly name: string;
  readonly label: string;
  readonly kind: SchemaApprovalFieldKind;
  readonly required: boolean;
  readonly description: string | null;
  readonly valuePreview: string | null;
};

export type SchemaApprovalModel = {
  readonly hasExplicitFields: boolean;
  readonly fields: ReadonlyArray<SchemaApprovalField>;
  readonly payloadPreview: ReadonlyArray<{ readonly key: string; readonly value: string }>;
  readonly outcomes: ReadonlyArray<string>;
};

export type BuildSchemaApprovalModelInput = {
  readonly schema: unknown;
  readonly payload: unknown;
  readonly outcomes: ReadonlyArray<string>;
};

type JsonObject = Record<string, unknown>;

const isObject = (value: unknown): value is JsonObject =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const stringArray = (value: unknown): ReadonlyArray<string> =>
  Array.isArray(value) ? value.filter((entry): entry is string => typeof entry === "string") : [];

const formatValue = (value: unknown): string | null => {
  if (value === undefined) return null;
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean" || value === null) return String(value);
  return JSON.stringify(value);
};

const fieldKind = (propertySchema: unknown): SchemaApprovalFieldKind => {
  if (!isObject(propertySchema)) return "unknown";
  const type = propertySchema.type;
  if (type === "integer") return "number";
  if (type === "string" || type === "number" || type === "boolean" || type === "array" || type === "object") {
    return type;
  }
  return "unknown";
};

const labelFor = (name: string): string => name.replaceAll("_", " ");

const payloadEntries = (payload: unknown): ReadonlyArray<{ readonly key: string; readonly value: string }> => {
  if (!isObject(payload)) return [];
  return Object.entries(payload).map(([key, value]) => ({
    key,
    value: formatValue(value) ?? "undefined",
  }));
};

export const buildSchemaApprovalModel = ({
  schema,
  payload,
  outcomes,
}: BuildSchemaApprovalModelInput): SchemaApprovalModel => {
  const required = isObject(schema) ? new Set(stringArray(schema.required)) : new Set<string>();
  const properties = isObject(schema) && isObject(schema.properties) ? schema.properties : null;
  const payloadObject = isObject(payload) ? payload : {};

  // This is projection, not validation. For loose schemas the product should
  // still show the recorded resume payload instead of inventing absent fields.
  const fields = properties
    ? Object.entries(properties).map(([name, propertySchema]): SchemaApprovalField => ({
      name,
      label: labelFor(name),
      kind: fieldKind(propertySchema),
      required: required.has(name),
      description: isObject(propertySchema) && typeof propertySchema.description === "string"
        ? propertySchema.description
        : null,
      valuePreview: formatValue(payloadObject[name]),
    }))
    : [];

  return {
    hasExplicitFields: fields.length > 0,
    fields,
    payloadPreview: payloadEntries(payload),
    outcomes,
  };
};
