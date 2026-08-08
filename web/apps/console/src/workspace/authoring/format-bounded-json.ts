const MAX_RAW_DRAFT_CHARS = 12_000;
const TRUNCATION_MARKER = "... truncated ...";

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

// Traverse until the display budget is exhausted so a large remote object is
// never fully materialized just to produce a clipped escape-hatch preview.
export const formatBoundedJson = (
  value: unknown,
  maxChars = MAX_RAW_DRAFT_CHARS,
): string => {
  const truncationMarker = TRUNCATION_MARKER.slice(0, Math.max(0, maxChars));
  const contentLimit = Math.max(0, maxChars);
  let output = "";
  let truncated = false;
  const activeObjects = new WeakSet<object>();

  const append = (chunk: string): void => {
    if (truncated) return;
    if (output.length + chunk.length > contentLimit) {
      output += chunk.slice(0, Math.max(0, contentLimit - output.length));
      truncated = true;
      return;
    }
    output += chunk;
  };

  const appendJsonString = (text: string): void => {
    append('"');
    for (let index = 0; index < text.length; index++) {
      if (truncated) return;
      const code = text.charCodeAt(index);
      if (code === 0x22) append('\\"');
      else if (code === 0x5c) append("\\\\");
      else if (code < 0x20) append(`\\u${code.toString(16).padStart(4, "0")}`);
      else if (code >= 0xd800 && code <= 0xdbff) {
        const nextCode = text.charCodeAt(index + 1);
        if (nextCode >= 0xdc00 && nextCode <= 0xdfff) {
          append(text.slice(index, index + 2));
          index++;
        } else append(`\\u${code.toString(16).padStart(4, "0")}`);
      } else if (code >= 0xdc00 && code <= 0xdfff) {
        append(`\\u${code.toString(16).padStart(4, "0")}`);
      } else append(text.charAt(index));
    }
    if (!truncated) append('"');
  };

  const visit = (current: unknown, depth: number): void => {
    if (truncated) return;
    if (current === null || typeof current !== "object") {
      if (typeof current === "string") appendJsonString(current);
      else if (typeof current === "number") append(Number.isFinite(current) ? String(current) : "null");
      else if (typeof current === "boolean") append(current ? "true" : "false");
      else append("null");
      return;
    }
    if (activeObjects.has(current)) {
      append('"[Circular]"');
      return;
    }
    activeObjects.add(current);
    const indent = "  ".repeat(depth);
    const childIndent = "  ".repeat(depth + 1);
    if (Array.isArray(current)) {
      append("[");
      let first = true;
      for (const item of current) {
        if (truncated) break;
        append(first ? `\n${childIndent}` : `,\n${childIndent}`);
        visit(item, depth + 1);
        first = false;
      }
      if (!truncated) append(first ? "]" : `\n${indent}]`);
    } else {
      if (!isRecord(current)) {
        activeObjects.delete(current);
        return;
      }
      const record = current;
      append("{");
      let first = true;
      for (const key in record) {
        if (!Object.prototype.hasOwnProperty.call(record, key) || truncated) continue;
        append(first ? `\n${childIndent}` : `,\n${childIndent}`);
        appendJsonString(key);
        append(": ");
        visit(record[key], depth + 1);
        first = false;
      }
      if (!truncated) append(first ? "}" : `\n${indent}}`);
    }
    activeObjects.delete(current);
  };

  visit(value, 0);
  if (!truncated) return output;
  const markerStart = Math.max(0, contentLimit - truncationMarker.length);
  return `${output.slice(0, markerStart)}${truncationMarker}`;
};
