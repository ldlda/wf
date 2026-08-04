import { Data, Either, Schema } from "effect";

export interface JsonObject {
  readonly [key: string]: JsonValue;
}

export type JsonValue =
  | boolean
  | null
  | number
  | string
  | readonly JsonValue[]
  | JsonObject;

export class JsonSchemaTranslationError extends Data.TaggedError(
  "JsonSchemaTranslationError",
)<{
  readonly keyword: string | null;
  readonly message: string;
  readonly path: string;
}> {}

export interface JsonSchemaTranslationOptions {
  readonly components?: Readonly<Record<string, unknown>>;
}

const isRecord = (value: unknown): value is Record<string, unknown> => {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return false;
  }
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
};

type NoContextStructField =
  | Schema.Schema.AnyNoContext
  | Schema.optional<Schema.Schema.AnyNoContext>;

const isJsonValue = (input: unknown): input is JsonValue => {
  const visiting = new Set<object>();
  const visit = (value: unknown): boolean => {
    if (
      value === null ||
      typeof value === "boolean" ||
      typeof value === "string"
    ) {
      return true;
    }
    if (typeof value === "number") return Number.isFinite(value);
    if (typeof value !== "object" || visiting.has(value)) return false;

    if (!Array.isArray(value) && !isRecord(value)) {
      return false;
    }
    if (Reflect.ownKeys(value).some((key) => typeof key !== "string")) {
      return false;
    }

    visiting.add(value);
    const valid = Array.isArray(value)
      ? value.every(visit)
      : Object.values(value).every(visit);
    visiting.delete(value);
    return valid;
  };
  return visit(input);
};

const JsonValueStructureSchema: Schema.Schema<JsonValue, JsonValue, never> =
  Schema.suspend(
    (): Schema.Schema<JsonValue, JsonValue, never> =>
      Schema.Union(
        Schema.String,
        Schema.JsonNumber,
        Schema.Boolean,
        Schema.Null,
        Schema.Array(JsonValueStructureSchema),
        Schema.Record({ key: Schema.String, value: JsonValueStructureSchema }),
      ),
  );

const JsonValueSchema: Schema.Schema<JsonValue, unknown, never> =
  Schema.Unknown.pipe(
    Schema.filter(isJsonValue, { message: () => "value must be valid JSON" }),
    Schema.transform(JsonValueStructureSchema, {
      strict: false,
      decode: (value) => value,
      encode: (value) => value,
    }),
  );

const RejectAllSchema = Schema.Unknown.pipe(
  Schema.filter(() => false, {
    message: () => "boolean false schema rejects all values",
  }),
);

const ANNOTATION_KEYWORDS = new Set([
  "default",
  "deprecated",
  "description",
  "examples",
  "title",
]);

const decodedObject = (
  fields: Readonly<Record<string, NoContextStructField>>,
  target: Schema.Schema.AnyNoContext,
  closed: boolean,
): Schema.Schema.AnyNoContext => {
  const allowedKeys = new Set(Object.keys(fields));
  const encodedObject = Schema.Unknown.pipe(
    Schema.filter(
      (value): value is Record<string, unknown> =>
        isRecord(value) &&
        (!closed || Object.keys(value).every((key) => allowedKeys.has(key))),
      {
        message: () =>
          closed
            ? "object contains an undeclared property"
            : "value must be a JSON object",
      },
    ),
  );

  // Validate the raw object before Struct can normalize away invalid inputs.
  return encodedObject.pipe(
    Schema.transform(JsonValueSchema, {
      strict: false,
      decode: (value) => value,
      encode: (value) => value,
    }),
    Schema.transform(target, {
      strict: false,
      decode: (value) => value,
      encode: (value) => value,
    }),
  );
};

const failure = (
  path: string,
  message: string,
  keyword: string | null = null,
): Either.Either<never, JsonSchemaTranslationError> =>
  Either.left(new JsonSchemaTranslationError({ keyword, message, path }));

const unsupportedKeyword = (
  value: Readonly<Record<string, unknown>>,
  allowed: ReadonlySet<string>,
  path: string,
): JsonSchemaTranslationError | null => {
  for (const keyword of Object.keys(value).sort()) {
    if (!ANNOTATION_KEYWORDS.has(keyword) && !allowed.has(keyword)) {
      return new JsonSchemaTranslationError({
        keyword,
        message: `unsupported JSON Schema keyword ${keyword}`,
        path,
      });
    }
  }
  return null;
};

const nonNegativeInteger = (
  value: unknown,
  keyword: string,
  path: string,
): Either.Either<number | undefined, JsonSchemaTranslationError> => {
  if (value === undefined) return Either.right(undefined);
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) {
    return failure(path, `${keyword} must be a non-negative integer`, keyword);
  }
  return Either.right(value);
};

const finiteNumber = (
  value: unknown,
  keyword: string,
  path: string,
): Either.Either<number | undefined, JsonSchemaTranslationError> => {
  if (value === undefined) return Either.right(undefined);
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return failure(path, `${keyword} must be a finite number`, keyword);
  }
  return Either.right(value);
};

type JsonLiteral = boolean | null | number | string;

type JsonPrimitiveType = "boolean" | "integer" | "null" | "number" | "string";

const literalAt = (
  value: unknown,
  path: string,
  keyword: string,
): Either.Either<JsonLiteral, JsonSchemaTranslationError> => {
  if (
    value === null ||
    typeof value === "boolean" ||
    typeof value === "string" ||
    (typeof value === "number" && Number.isFinite(value))
  ) {
    return Either.right(value);
  }
  return failure(
    path,
    `${keyword} currently supports only JSON primitive values`,
    keyword,
  );
};

const primitiveTypeAt = (
  value: unknown,
  path: string,
): Either.Either<JsonPrimitiveType | undefined, JsonSchemaTranslationError> => {
  if (value === undefined) return Either.right(undefined);
  if (
    value === "boolean" ||
    value === "integer" ||
    value === "null" ||
    value === "number" ||
    value === "string"
  ) {
    return Either.right(value);
  }
  return failure(path, "const and enum require a primitive declared type", "type");
};

const literalMatchesType = (
  literal: JsonLiteral,
  declaredType: JsonPrimitiveType | undefined,
): boolean => {
  switch (declaredType) {
    case undefined:
      return true;
    case "boolean":
      return typeof literal === "boolean";
    case "integer":
      return typeof literal === "number" && Number.isInteger(literal);
    case "null":
      return literal === null;
    case "number":
      return typeof literal === "number";
    case "string":
      return typeof literal === "string";
  }
};

// JSON Schema measures string length in Unicode code points, not UTF-16 units.
const codePointLength = (value: string): number => Array.from(value).length;

class Translator {
  readonly #cache = new Map<string, Schema.Schema.AnyNoContext>();
  readonly #components: Readonly<Record<string, unknown>>;
  readonly #resolvingAtDepth = new Map<string, number>();

  constructor(components: Readonly<Record<string, unknown>>) {
    this.#components = components;
  }

  translate(
    value: unknown,
    path = "$",
    structuralDepth = 0,
  ): Either.Either<Schema.Schema.AnyNoContext, JsonSchemaTranslationError> {
    if (value === true) return Either.right(JsonValueSchema);
    if (value === false) return Either.right(RejectAllSchema);
    if (!isRecord(value)) {
      return failure(path, "JSON Schema must be a boolean or object");
    }

    for (const keyword of ["allOf", "if", "not", "oneOf", "then", "else"]) {
      if (keyword in value) {
        return failure(
          path,
          `${keyword} is not supported by the representative translator`,
          keyword,
        );
      }
    }

    if ("$ref" in value) {
      return this.#translateRef(value, path, structuralDepth);
    }
    if ("anyOf" in value) {
      return this.#translateAnyOf(value, path, structuralDepth);
    }
    if ("const" in value) return this.#translateConst(value, path);
    if ("enum" in value) return this.#translateEnum(value, path);

    if (!("type" in value)) {
      const unsupported = unsupportedKeyword(value, new Set(), path);
      return unsupported === null
        ? Either.right(JsonValueSchema)
        : Either.left(unsupported);
    }
    if (typeof value.type !== "string") {
      return failure(path, "type must be a single string", "type");
    }

    switch (value.type) {
      case "array":
        return this.#translateArray(value, path, structuralDepth);
      case "boolean":
        return this.#translateBoolean(value, path);
      case "integer":
        return this.#translateNumber(value, path, true);
      case "null":
        return this.#translateNull(value, path);
      case "number":
        return this.#translateNumber(value, path, false);
      case "object":
        return this.#translateObject(value, path, structuralDepth);
      case "string":
        return this.#translateString(value, path);
      default:
        return failure(path, `unsupported JSON Schema type ${value.type}`, "type");
    }
  }

  #translateRef(
    value: Readonly<Record<string, unknown>>,
    path: string,
    structuralDepth: number,
  ): Either.Either<Schema.Schema.AnyNoContext, JsonSchemaTranslationError> {
    const unsupported = unsupportedKeyword(value, new Set(["$ref"]), path);
    if (unsupported !== null) return Either.left(unsupported);
    if (typeof value.$ref !== "string") {
      return failure(path, "$ref must be a string", "$ref");
    }
    const prefix = "#/components/schemas/";
    if (!value.$ref.startsWith(prefix)) {
      return failure(
        path,
        "only local component schema references are supported",
        "$ref",
      );
    }
    const name = value.$ref.slice(prefix.length);
    if (
      name.length === 0 ||
      name.includes("/") ||
      !Object.hasOwn(this.#components, name)
    ) {
      return failure(path, `missing component schema ${name || "<empty>"}`, "$ref");
    }

    const cached = this.#cache.get(name);
    if (cached !== undefined) return Either.right(cached);
    const resolvingDepth = this.#resolvingAtDepth.get(name);
    if (resolvingDepth !== undefined) {
      if (structuralDepth <= resolvingDepth) {
        return failure(
          path,
          "recursive $ref requires an intervening structural boundary",
          "$ref",
        );
      }
      // Runtime migration must bound input depth before exposing recursive
      // schemas; Effect's decoder recursion is not independently depth-limited.
      return Either.right(
        Schema.suspend(() => this.#cache.get(name) ?? RejectAllSchema),
      );
    }

    this.#resolvingAtDepth.set(name, structuralDepth);
    const translated = this.translate(
      this.#components[name],
      `#/components/schemas/${name}`,
      structuralDepth,
    );
    this.#resolvingAtDepth.delete(name);
    if (Either.isRight(translated)) this.#cache.set(name, translated.right);
    return translated;
  }

  #translateAnyOf(
    value: Readonly<Record<string, unknown>>,
    path: string,
    structuralDepth: number,
  ): Either.Either<Schema.Schema.AnyNoContext, JsonSchemaTranslationError> {
    const unsupported = unsupportedKeyword(value, new Set(["anyOf"]), path);
    if (unsupported !== null) return Either.left(unsupported);
    if (!Array.isArray(value.anyOf) || value.anyOf.length === 0) {
      return failure(path, "anyOf must be a non-empty array", "anyOf");
    }
    const members: Schema.Schema.AnyNoContext[] = [];
    for (const [index, member] of value.anyOf.entries()) {
      const translated = this.translate(
        member,
        `${path}.anyOf[${index}]`,
        structuralDepth,
      );
      if (Either.isLeft(translated)) return translated;
      members.push(translated.right);
    }
    return Either.right(Schema.Union(...members));
  }

  #translateConst(
    value: Readonly<Record<string, unknown>>,
    path: string,
  ): Either.Either<Schema.Schema.AnyNoContext, JsonSchemaTranslationError> {
    const unsupported = unsupportedKeyword(value, new Set(["const", "type"]), path);
    if (unsupported !== null) return Either.left(unsupported);
    const declaredType = primitiveTypeAt(value.type, path);
    if (Either.isLeft(declaredType)) return Either.left(declaredType.left);
    const literal = literalAt(value.const, path, "const");
    if (Either.isLeft(literal)) return Either.left(literal.left);
    if (!literalMatchesType(literal.right, declaredType.right)) {
      return failure(path, "const contradicts its declared type", "type");
    }
    return Either.right(Schema.Literal(literal.right));
  }

  #translateEnum(
    value: Readonly<Record<string, unknown>>,
    path: string,
  ): Either.Either<Schema.Schema.AnyNoContext, JsonSchemaTranslationError> {
    const unsupported = unsupportedKeyword(value, new Set(["enum", "type"]), path);
    if (unsupported !== null) return Either.left(unsupported);
    if (!Array.isArray(value.enum) || value.enum.length === 0) {
      return failure(path, "enum must be a non-empty array", "enum");
    }
    const declaredType = primitiveTypeAt(value.type, path);
    if (Either.isLeft(declaredType)) return Either.left(declaredType.left);
    const literals: JsonLiteral[] = [];
    for (const [index, member] of value.enum.entries()) {
      const literal = literalAt(member, `${path}.enum[${index}]`, "enum");
      if (Either.isLeft(literal)) return Either.left(literal.left);
      if (!literalMatchesType(literal.right, declaredType.right)) {
        return failure(path, "enum member contradicts its declared type", "type");
      }
      literals.push(literal.right);
    }
    if (new Set(literals).size !== literals.length) {
      return failure(path, "enum values must be unique", "enum");
    }
    return Either.right(Schema.Literal(...literals));
  }

  #translateString(
    value: Readonly<Record<string, unknown>>,
    path: string,
  ): Either.Either<Schema.Schema.AnyNoContext, JsonSchemaTranslationError> {
    const unsupported = unsupportedKeyword(
      value,
      new Set(["maxLength", "minLength", "pattern", "type"]),
      path,
    );
    if (unsupported !== null) return Either.left(unsupported);
    const minLength = nonNegativeInteger(value.minLength, "minLength", path);
    if (Either.isLeft(minLength)) return Either.left(minLength.left);
    const maxLength = nonNegativeInteger(value.maxLength, "maxLength", path);
    if (Either.isLeft(maxLength)) return Either.left(maxLength.left);
    const pattern = value.pattern;
    if (typeof pattern !== "string" && pattern !== undefined) {
      return failure(path, "pattern must be a string", "pattern");
    }
    const regex: Either.Either<RegExp | undefined, JsonSchemaTranslationError> =
      pattern === undefined
        ? Either.right(undefined)
        : Either.try({
            try: () => new RegExp(pattern),
            catch: () =>
              new JsonSchemaTranslationError({
                keyword: "pattern",
                message: "pattern must be a valid regular expression",
                path,
              }),
          });
    if (Either.isLeft(regex)) return Either.left(regex.left);

    return Either.right(
      Schema.String.pipe(
        Schema.filter(
          (text) =>
            (minLength.right === undefined ||
              codePointLength(text) >= minLength.right) &&
            (maxLength.right === undefined ||
              codePointLength(text) <= maxLength.right) &&
            (regex.right === undefined || regex.right.test(text)),
          { message: () => "string does not satisfy JSON Schema constraints" },
        ),
      ),
    );
  }

  #translateNumber(
    value: Readonly<Record<string, unknown>>,
    path: string,
    integer: boolean,
  ): Either.Either<Schema.Schema.AnyNoContext, JsonSchemaTranslationError> {
    const unsupported = unsupportedKeyword(
      value,
      new Set([
        "exclusiveMaximum",
        "exclusiveMinimum",
        "maximum",
        "minimum",
        "type",
      ]),
      path,
    );
    if (unsupported !== null) return Either.left(unsupported);
    const minimum = finiteNumber(value.minimum, "minimum", path);
    if (Either.isLeft(minimum)) return Either.left(minimum.left);
    const maximum = finiteNumber(value.maximum, "maximum", path);
    if (Either.isLeft(maximum)) return Either.left(maximum.left);
    const exclusiveMinimum = finiteNumber(
      value.exclusiveMinimum,
      "exclusiveMinimum",
      path,
    );
    if (Either.isLeft(exclusiveMinimum)) return Either.left(exclusiveMinimum.left);
    const exclusiveMaximum = finiteNumber(
      value.exclusiveMaximum,
      "exclusiveMaximum",
      path,
    );
    if (Either.isLeft(exclusiveMaximum)) return Either.left(exclusiveMaximum.left);

    return Either.right(
      Schema.JsonNumber.pipe(
        Schema.filter(
          (number) =>
            (!integer || Number.isInteger(number)) &&
            (minimum.right === undefined || number >= minimum.right) &&
            (maximum.right === undefined || number <= maximum.right) &&
            (exclusiveMinimum.right === undefined || number > exclusiveMinimum.right) &&
            (exclusiveMaximum.right === undefined || number < exclusiveMaximum.right),
          { message: () => "number does not satisfy JSON Schema constraints" },
        ),
      ),
    );
  }

  #translateArray(
    value: Readonly<Record<string, unknown>>,
    path: string,
    structuralDepth: number,
  ): Either.Either<Schema.Schema.AnyNoContext, JsonSchemaTranslationError> {
    const unsupported = unsupportedKeyword(
      value,
      new Set(["items", "maxItems", "minItems", "type"]),
      path,
    );
    if (unsupported !== null) return Either.left(unsupported);
    if (!("items" in value)) {
      return failure(path, "array schemas must declare items", "items");
    }
    const items = this.translate(value.items, `${path}.items`, structuralDepth + 1);
    if (Either.isLeft(items)) return items;
    const minItems = nonNegativeInteger(value.minItems, "minItems", path);
    if (Either.isLeft(minItems)) return Either.left(minItems.left);
    const maxItems = nonNegativeInteger(value.maxItems, "maxItems", path);
    if (Either.isLeft(maxItems)) return Either.left(maxItems.left);

    return Either.right(
      Schema.Array(items.right).pipe(
        Schema.filter(
          (array) =>
            (minItems.right === undefined || array.length >= minItems.right) &&
            (maxItems.right === undefined || array.length <= maxItems.right),
          { message: () => "array does not satisfy JSON Schema constraints" },
        ),
      ),
    );
  }

  #translateObject(
    value: Readonly<Record<string, unknown>>,
    path: string,
    structuralDepth: number,
  ): Either.Either<Schema.Schema.AnyNoContext, JsonSchemaTranslationError> {
    const unsupported = unsupportedKeyword(
      value,
      new Set(["additionalProperties", "properties", "required", "type"]),
      path,
    );
    if (unsupported !== null) return Either.left(unsupported);
    const properties = value.properties ?? {};
    if (!isRecord(properties)) {
      return failure(path, "properties must be an object", "properties");
    }
    for (const name of Object.keys(properties)) {
      if (Object.hasOwn(Object.prototype, name)) {
        return failure(
          path,
          `property name ${name} collides with the object prototype`,
          "properties",
        );
      }
    }
    const requiredValue = value.required ?? [];
    if (!Array.isArray(requiredValue)) {
      return failure(path, "required must be an array of property names", "required");
    }
    const requiredNames: string[] = [];
    for (const item of requiredValue) {
      if (typeof item !== "string") {
        return failure(path, "required must be an array of property names", "required");
      }
      requiredNames.push(item);
    }
    const required = new Set(requiredNames);
    if (required.size !== requiredNames.length) {
      return failure(path, "required property names must be unique", "required");
    }
    for (const name of required) {
      if (!Object.hasOwn(properties, name)) {
        return failure(
          path,
          `required property ${name} outside properties is not supported yet`,
          "required",
        );
      }
    }

    const fieldEntries: Array<[string, NoContextStructField]> = [];
    for (const name of Object.keys(properties).sort()) {
      const property = this.translate(
        properties[name],
        `${path}.properties.${name}`,
        structuralDepth + 1,
      );
      if (Either.isLeft(property)) return property;
      fieldEntries.push([
        name,
        required.has(name) ? property.right : Schema.optional(property.right),
      ]);
    }
    const fields = Object.fromEntries(fieldEntries);

    const additionalProperties = value.additionalProperties ?? true;
    if (additionalProperties === false) {
      return Either.right(decodedObject(fields, Schema.Struct(fields), true));
    }
    if (additionalProperties === true) {
      return Either.right(
        decodedObject(
          fields,
          Schema.Struct(
            fields,
            Schema.Record({ key: Schema.String, value: JsonValueSchema }),
          ),
          false,
        ),
      );
    }
    if (!isRecord(additionalProperties)) {
      return failure(
        path,
        "additionalProperties must be a boolean or schema object",
        "additionalProperties",
      );
    }
    if (Object.keys(properties).length > 0) {
      return failure(
        path,
        "typed additionalProperties with fixed properties is not supported yet",
        "additionalProperties",
      );
    }
    const rest = this.translate(
      additionalProperties,
      `${path}.additionalProperties`,
      structuralDepth + 1,
    );
    if (Either.isLeft(rest)) return rest;
    return Either.right(
      decodedObject(
        fields,
        Schema.Record({ key: Schema.String, value: rest.right }),
        false,
      ),
    );
  }

  #translateBoolean(
    value: Readonly<Record<string, unknown>>,
    path: string,
  ): Either.Either<Schema.Schema.AnyNoContext, JsonSchemaTranslationError> {
    const unsupported = unsupportedKeyword(value, new Set(["type"]), path);
    return unsupported === null
      ? Either.right(Schema.Boolean)
      : Either.left(unsupported);
  }

  #translateNull(
    value: Readonly<Record<string, unknown>>,
    path: string,
  ): Either.Either<Schema.Schema.AnyNoContext, JsonSchemaTranslationError> {
    const unsupported = unsupportedKeyword(value, new Set(["type"]), path);
    return unsupported === null ? Either.right(Schema.Null) : Either.left(unsupported);
  }
}

/**
 * Translates the manifest's representative JSON Schema subset without
 * weakening unsupported constraints. Callers must handle the typed failure
 * before exposing the resulting Effect schema at a runtime boundary.
 */
export const translateJsonSchema = (
  schema: unknown,
  options: JsonSchemaTranslationOptions = {},
): Either.Either<Schema.Schema.AnyNoContext, JsonSchemaTranslationError> =>
  new Translator(options.components ?? {}).translate(schema);
