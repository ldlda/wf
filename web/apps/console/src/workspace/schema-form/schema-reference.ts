type SchemaRecord = Record<string, unknown>;

export type SchemaReferenceResolution =
  | { readonly ok: true; readonly schema: unknown }
  | { readonly ok: false; readonly reason: string };

export type SchemaReferenceTraversalResolution =
  | {
      readonly ok: true;
      readonly schema: unknown;
      readonly referenceAncestry: ReadonlySet<string>;
    }
  | { readonly ok: false; readonly reason: string };

const ANNOTATION_KEYS = ["title", "description", "default"] as const;

const isRecord = (value: unknown): value is SchemaRecord =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const hasOwn = (value: SchemaRecord, key: string): boolean =>
  Object.prototype.hasOwnProperty.call(value, key);

const failure = (
  reason: string,
): { readonly ok: false; readonly reason: string } => ({
  ok: false,
  reason,
});

const decodePointer = (pointer: string): string[] | null => {
  const tokens = pointer.slice(2).split("/");
  const decodedTokens: string[] = [];
  for (const token of tokens) {
    let decoded = "";
    for (let index = 0; index < token.length; index += 1) {
      const character = token[index];
      if (character !== "~") {
        decoded += character;
        continue;
      }
      const escape = token[index + 1];
      if (escape !== "0" && escape !== "1") return null;
      decoded += escape === "0" ? "~" : "/";
      index += 1;
    }
    decodedTokens.push(decoded);
  }
  return decodedTokens;
};

type PointerLookup =
  | { readonly ok: true; readonly value: unknown }
  | { readonly ok: false; readonly malformed: boolean };

const pointerTarget = (rootSchema: unknown, ref: string): PointerLookup => {
  const tokens = decodePointer(ref);
  if (tokens === null) return { ok: false, malformed: true };

  let current: unknown = rootSchema;
  for (const token of tokens) {
    if (Array.isArray(current)) {
      if (!/^(0|[1-9]\d*)$/.test(token)) return { ok: false, malformed: true };
      const index = Number(token);
      if (
        !Number.isSafeInteger(index) ||
        !Object.prototype.hasOwnProperty.call(current, index)
      ) {
        return { ok: false, malformed: false };
      }
      current = current[index];
      continue;
    }
    if (!isRecord(current) || !hasOwn(current, token))
      return { ok: false, malformed: false };
    current = current[token];
  }
  return { ok: true, value: current };
};

const hasStructuralSiblings = (schemaNode: SchemaRecord): boolean =>
  Object.keys(schemaNode).some(
    (key) =>
      key !== "$ref" &&
      !(ANNOTATION_KEYS as ReadonlyArray<string>).includes(key),
  );

const mergeAnnotations = (
  schema: unknown,
  referenceNode: SchemaRecord,
): unknown => {
  if (!isRecord(schema)) return schema;
  const annotations = Object.fromEntries(
    ANNOTATION_KEYS.filter((key) => hasOwn(referenceNode, key)).map((key) => [
      key,
      referenceNode[key],
    ]),
  );
  return Object.keys(annotations).length === 0
    ? schema
    : { ...schema, ...annotations };
};

const resolveNode = (
  rootSchema: unknown,
  schemaNode: unknown,
  referenceAncestry: ReadonlySet<string>,
): SchemaReferenceTraversalResolution => {
  if (!isRecord(schemaNode) || !hasOwn(schemaNode, "$ref")) {
    return { ok: true, schema: schemaNode, referenceAncestry };
  }

  const ref = schemaNode.$ref;
  if (typeof ref !== "string")
    return failure("Malformed local schema reference pointer.");
  if (/^[A-Za-z][A-Za-z\d+.-]*:/.test(ref)) {
    return failure("External schema references are not supported.");
  }
  if (!ref.startsWith("#")) {
    return failure("External schema references are not supported.");
  }
  if (!ref.startsWith("#/")) {
    return failure("Only local JSON Pointer schema references are supported.");
  }
  if (hasStructuralSiblings(schemaNode)) {
    return failure("Structural siblings beside $ref are not supported.");
  }
  if (referenceAncestry.has(ref))
    return failure("Local schema reference cycle detected.");

  const target = pointerTarget(rootSchema, ref);
  if (!target.ok) {
    return failure(
      target.malformed
        ? "Malformed local schema reference pointer."
        : "Local schema reference target was not found.",
    );
  }

  // Keep references active for structural child descent. Callers pass the
  // resulting immutable ancestry to each child, so sibling reuse stays valid.
  const nextAncestry = new Set(referenceAncestry);
  nextAncestry.add(ref);
  const resolved = resolveNode(rootSchema, target.value, nextAncestry);
  if (!resolved.ok) return resolved;
  return {
    ok: true,
    schema: mergeAnnotations(resolved.schema, schemaNode),
    referenceAncestry: resolved.referenceAncestry,
  };
};

export const resolveLocalSchemaNodeWithAncestry = (
  rootSchema: unknown,
  schemaNode: unknown,
  referenceAncestry: ReadonlySet<string>,
): SchemaReferenceTraversalResolution =>
  resolveNode(rootSchema, schemaNode, referenceAncestry);

export const resolveLocalSchemaNode = (
  rootSchema: unknown,
  schemaNode: unknown,
): SchemaReferenceResolution => {
  const resolution = resolveLocalSchemaNodeWithAncestry(
    rootSchema,
    schemaNode,
    new Set(),
  );
  return resolution.ok
    ? { ok: true, schema: resolution.schema }
    : resolution;
};
