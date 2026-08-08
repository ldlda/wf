export type SchemaPathPart = string | number;

const BARE_TOML_KEY = /^[A-Za-z0-9_-]+$/;
const CONTROL_CHARACTER = /[\u0000-\u001f\u007f]/;

const isBareSegment = (value: string): boolean => BARE_TOML_KEY.test(value);

const isValidSegment = (value: string): boolean =>
  value.trim().length > 0 && !CONTROL_CHARACTER.test(value);

const parseDoubleQuoted = (raw: string, start: number): { readonly value: string; readonly next: number } | null => {
  let escaped = false;
  for (let index = start + 1; index < raw.length; index++) {
    const character = raw[index];
    if (escaped) {
      escaped = false;
      continue;
    }
    if (character === "\\") {
      escaped = true;
      continue;
    }
    if (character === '"') {
      const encoded = raw.slice(start, index + 1);
      try {
        const parsed: unknown = JSON.parse(encoded);
        return typeof parsed === "string" && isValidSegment(parsed)
          ? { value: parsed, next: index + 1 }
          : null;
      } catch {
        return null;
      }
    }
  }
  return null;
};

const parseSingleQuoted = (raw: string, start: number): { readonly value: string; readonly next: number } | null => {
  let value = "";
  for (let index = start + 1; index < raw.length; index++) {
    const character = raw[index];
    if (character === "'") {
      if (raw[index + 1] === "'") {
        value += "'";
        index++;
        continue;
      }
      return isValidSegment(value) ? { value, next: index + 1 } : null;
    }
    value += character;
  }
  return null;
};

/** Parse the canonical TOML-key path grammar used by workflow paths. */
export const parseTOMLPath = (raw: string): ReadonlyArray<string> | null => {
  if (raw === ".") return [];
  if (raw.length === 0 || raw.trim() !== raw) return null;

  const parts: string[] = [];
  let index = 0;
  while (index < raw.length) {
    const character = raw[index];
    let parsed: { readonly value: string; readonly next: number } | null;
    if (character === '"') parsed = parseDoubleQuoted(raw, index);
    else if (character === "'") parsed = parseSingleQuoted(raw, index);
    else {
      const start = index;
      while (index < raw.length && raw[index] !== ".") index++;
      const value = raw.slice(start, index);
      parsed = isBareSegment(value) ? { value, next: index } : null;
    }
    if (!parsed) return null;
    parts.push(parsed.value);
    index = parsed.next;
    if (index === raw.length) return parts;
    if (raw[index] !== ".") return null;
    index++;
    if (index === raw.length) return null;
  }
  return null;
};

/** Format literal schema path segments using the canonical TOML-key syntax. */
export const formatTOMLPath = (parts: ReadonlyArray<SchemaPathPart>): string => {
  if (parts.length === 0) return ".";
  return parts
    .map((part) => {
      if (typeof part === "number") return String(part);
      if (isBareSegment(part)) return part;
      const encoded = JSON.stringify(part);
      return encoded ?? '""';
    })
    .join(".");
};

export const parseGraphSourcePath = (raw: string): ReadonlyArray<string> | null => {
  const parts = parseTOMLPath(raw);
  return parts && parts.length > 0 && (parts[0] === "input" || parts[0] === "state" || parts[0] === "context")
    ? parts
    : null;
};

/** Encode path segment type and contents so valid schema paths cannot collide. */
export const encodeSchemaPath = (parts: ReadonlyArray<SchemaPathPart>): string => {
  if (parts.length === 0) return "root";
  return parts
    .map((part) => {
      const text = String(part);
      const codePoints = Array.from(text).map((character) => character.codePointAt(0)?.toString(16) ?? "0");
      return `${typeof part === "number" ? "n" : "s"}${text.length}_${codePoints.join("-")}`;
    })
    .join("__");
};
