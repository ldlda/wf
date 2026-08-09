export type SchemaField = {
  readonly path: ReadonlyArray<string | number>;
  readonly key: string;
  readonly title: string;
  readonly description: string | null;
  readonly kind: "string" | "number" | "integer" | "boolean" | "enum" | "object" | "array" | "json";
  readonly required: boolean;
  readonly hasDefault: boolean;
  readonly defaultValue: unknown;
  readonly enumValues: ReadonlyArray<string | number | boolean | null>;
  readonly children: ReadonlyArray<SchemaField>;
  readonly item: SchemaField | null;
  readonly fallbackReason: string | null;
};

export type FieldSource =
  | { readonly mode: "literal"; readonly value: unknown }
  | { readonly mode: "bind"; readonly sourcePath: string };

export const rebaseSchemaField = (
  field: SchemaField,
  path: ReadonlyArray<string | number>,
): SchemaField => {
  const relativePath = (childPath: ReadonlyArray<string | number>): ReadonlyArray<string | number> =>
    childPath.slice(field.path.length);
  const children = field.children.map((child) =>
    rebaseSchemaField(child, [...path, ...relativePath(child.path)]),
  );
  const item = field.item
    ? rebaseSchemaField(field.item, [...path, ...relativePath(field.item.path)])
    : null;
  return { ...field, path, children, item };
};

type SchemaRecord = Record<string, unknown>;
type EnumValue = string | number | boolean | null;

const isRecord = (value: unknown): value is SchemaRecord =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const hasOwn = (value: SchemaRecord, key: string): boolean =>
  Object.prototype.hasOwnProperty.call(value, key);

const stringValue = (value: unknown): string | null =>
  typeof value === "string" ? value : null;

const isEnumValue = (value: unknown): value is EnumValue =>
  value === null ||
  typeof value === "string" ||
  typeof value === "boolean" ||
  (typeof value === "number" && Number.isFinite(value));

const fallback = (
  schema: unknown,
  path: ReadonlyArray<string | number>,
  key: string,
  required: boolean,
  title: string,
  reason: string,
): SchemaField => ({
  path,
  key,
  title,
  description: isRecord(schema) ? stringValue(schema.description) : null,
  kind: "json",
  required,
  hasDefault: isRecord(schema) && hasOwn(schema, "default"),
  defaultValue: isRecord(schema) ? schema.default : undefined,
  enumValues: [],
  children: [],
  item: null,
  fallbackReason: reason,
});

const unsupportedReason = (schema: SchemaRecord): string | null => {
  if (hasOwn(schema, "$ref")) {
    return "The schema contains an unresolved $ref, which the native form cannot represent.";
  }
  if (hasOwn(schema, "oneOf")) {
    return "The schema uses oneOf, which the native form cannot represent.";
  }
  if (hasOwn(schema, "anyOf")) {
    return "The schema uses anyOf, which the native form cannot represent.";
  }
  if (hasOwn(schema, "allOf")) {
    return "The schema uses allOf, which the native form cannot represent.";
  }
  if (hasOwn(schema, "not")) {
    return "The schema uses not, which the native form cannot represent.";
  }
  if (hasOwn(schema, "if") || hasOwn(schema, "then") || hasOwn(schema, "else")) {
    return "The schema uses conditional keywords, which the native form cannot represent.";
  }
  return null;
};

const requiredPropertyNames = (schema: SchemaRecord): ReadonlySet<string> => {
  const required = schema.required;
  if (!Array.isArray(required)) return new Set();
  return new Set(required.filter((value): value is string => typeof value === "string"));
};

const normalizeField = (
  schema: unknown,
  path: ReadonlyArray<string | number>,
  key: string,
  required: boolean,
  defaultTitle: string,
): SchemaField => {
  const title = isRecord(schema) ? stringValue(schema.title) ?? defaultTitle : defaultTitle;
  if (!isRecord(schema)) {
    return fallback(schema, path, key, required, title, "The schema is not a JSON object; edit JSON directly.");
  }

  const reason = unsupportedReason(schema);
  if (reason) return fallback(schema, path, key, required, title, reason);

  const enumValue = schema.enum;
  if (Array.isArray(enumValue) && enumValue.every(isEnumValue)) {
    return {
      path,
      key,
      title,
      description: stringValue(schema.description),
      kind: "enum",
      required,
      hasDefault: hasOwn(schema, "default"),
      defaultValue: schema.default,
      enumValues: enumValue,
      children: [],
      item: null,
      fallbackReason: null,
    };
  }

  const type = schema.type;
  if (type === undefined) {
    return fallback(schema, path, key, required, title, "The schema is unconstrained; edit JSON directly.");
  }

  if (type === "object") {
    const properties = schema.properties;
    if (properties !== undefined && !isRecord(properties)) {
      return fallback(schema, path, key, required, title, "The schema has invalid properties; edit JSON directly.");
    }
    const requiredNames = requiredPropertyNames(schema);
    const children = properties
      ? Object.entries(properties).map(([propertyKey, propertySchema]) =>
          normalizeField(
            propertySchema,
            [...path, propertyKey],
            propertyKey,
            requiredNames.has(propertyKey),
            stringValue(propertySchema && isRecord(propertySchema) ? propertySchema.title : null) ?? propertyKey,
          ),
        )
      : [];
    return {
      path,
      key,
      title,
      description: stringValue(schema.description),
      kind: "object",
      required,
      hasDefault: hasOwn(schema, "default"),
      defaultValue: schema.default,
      enumValues: [],
      children,
      item: null,
      fallbackReason: null,
    };
  }

  if (type === "array") {
    const itemSchema = schema.items;
    if (itemSchema === undefined) {
      return fallback(schema, path, key, required, title, "The array has no item schema; edit JSON directly.");
    }
    const item = normalizeField(itemSchema, [...path, 0], "item", true, `${title} item`);
    return {
      path,
      key,
      title,
      description: stringValue(schema.description),
      kind: "array",
      required,
      hasDefault: hasOwn(schema, "default"),
      defaultValue: schema.default,
      enumValues: [],
      children: [],
      item,
      fallbackReason: null,
    };
  }

  if (type === "string" || type === "number" || type === "integer" || type === "boolean") {
    return {
      path,
      key,
      title,
      description: stringValue(schema.description),
      kind: type,
      required,
      hasDefault: hasOwn(schema, "default"),
      defaultValue: schema.default,
      enumValues: [],
      children: [],
      item: null,
      fallbackReason: null,
    };
  }

  return fallback(schema, path, key, required, title, "The schema type is unsupported; edit JSON directly.");
};

export const normalizeSchemaField = (
  schema: unknown,
  path: ReadonlyArray<string | number> = [],
  key = "root",
  required = true,
): SchemaField => normalizeField(schema, path, key, required, key === "root" ? "Value" : key);

export const normalizeSchema = (schema: unknown): SchemaField =>
  normalizeSchemaField(schema);

/** Find a normalized field without losing the array index in the returned path. */
export const schemaFieldAtPath = (
  root: SchemaField,
  path: ReadonlyArray<string | number>,
): SchemaField | null => {
  let current = root;
  const actualPath: Array<string | number> = [];
  for (const part of path) {
    if (current.kind === "object") {
      const child = current.children.find((candidate) => candidate.key === String(part));
      if (child === undefined) return null;
      current = child;
      actualPath.push(child.key);
      continue;
    }
    if (current.kind === "array" && current.item !== null) {
      const index = typeof part === "number" ? part : Number(part);
      if (!Number.isSafeInteger(index) || index < 0) return null;
      current = rebaseSchemaField(current.item, [...actualPath, index]);
      actualPath.push(index);
      continue;
    }
    return null;
  }
  return current;
};
