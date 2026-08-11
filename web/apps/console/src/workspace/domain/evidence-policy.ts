import type { EvidenceRecord } from "../../app/state.js";

export const EVIDENCE_MAX_BYTES = 32 * 1024;
export const EVIDENCE_MAX_RECORDS = 100;

const MAX_DEPTH = 8;
const MAX_STRING_LENGTH = 4096;
const MAX_ENTRIES = 100;
const REDACTED_MARKER = "[redacted]";
const DEPTH_LIMIT_MARKER = "[truncated: depth limit]";
const EVIDENCE_LIMIT_MARKER = "[truncated: evidence limit]";
const CIRCULAR_MARKER = "[truncated: circular reference]";
const UNSUPPORTED_MARKER = "[unsupported: value]";
const TRUNCATION_KEY = EVIDENCE_LIMIT_MARKER;

const sensitiveKeys = new Set([
  "authorization",
  "cookie",
  "set-cookie",
  "token",
  "access_token",
  "refresh_token",
  "secret",
  "password",
  "api_key",
  "api-key",
]);

const isSensitiveKey = (key: string): boolean => sensitiveKeys.has(key.toLowerCase());

const byteLength = (value: unknown): number => {
  const serialized = JSON.stringify(value);
  return new TextEncoder().encode(serialized).length;
};

const truncateString = (value: string, maxLength: number): string => {
  const characters = Array.from(value);
  if (characters.length <= maxLength) return value;
  const prefixLength = Math.max(0, maxLength - EVIDENCE_LIMIT_MARKER.length);
  return `${characters.slice(0, prefixLength).join("")}${EVIDENCE_LIMIT_MARKER}`;
};

const unsupportedValue = (value: unknown): string => {
  if (value === undefined) return "[unsupported: undefined]";
  if (typeof value === "function") return "[unsupported: function]";
  if (typeof value === "symbol") return "[unsupported: symbol]";
  if (typeof value === "bigint") return "[unsupported: bigint]";
  return UNSUPPORTED_MARKER;
};

const readProperty = (value: object, key: string): unknown => {
  try {
    return Reflect.get(value, key);
  } catch {
    return "[unavailable: evidence value]";
  }
};

const projectValue = (
  value: unknown,
  depth: number,
  active: WeakSet<object>,
): unknown => {
  if (value === null) return null;

  switch (typeof value) {
    case "string":
      return truncateString(value, MAX_STRING_LENGTH);
    case "boolean":
      return value;
    case "number":
      return Number.isFinite(value) ? value : "[unsupported: number]";
    case "undefined":
    case "function":
    case "symbol":
    case "bigint":
      return unsupportedValue(value);
    case "object":
      break;
  }

  if (depth >= MAX_DEPTH) return DEPTH_LIMIT_MARKER;
  if (active.has(value)) return CIRCULAR_MARKER;

  active.add(value);
  try {
    if (Array.isArray(value)) {
      const result: unknown[] = [];
      const length = Math.min(value.length, MAX_ENTRIES);
      for (let index = 0; index < length; index += 1) {
        result.push(projectValue(readProperty(value, index.toString()), depth + 1, active));
      }
      if (value.length > MAX_ENTRIES) result.push(EVIDENCE_LIMIT_MARKER);
      return result;
    }

    const result: Record<string, unknown> = {};
    let keys: string[];
    try {
      keys = Object.keys(value);
    } catch {
      return UNSUPPORTED_MARKER;
    }
    const length = Math.min(keys.length, MAX_ENTRIES);
    for (let index = 0; index < length; index += 1) {
      const key = keys[index];
      if (key === undefined) continue;
      const safeKey = truncateString(key, MAX_STRING_LENGTH);
      // Check the key before reading its value so secrets behind getters or cycles are never traversed.
      result[safeKey] = isSensitiveKey(key)
        ? REDACTED_MARKER
        : projectValue(readProperty(value, key), depth + 1, active);
    }
    if (keys.length > MAX_ENTRIES) result[TRUNCATION_KEY] = EVIDENCE_LIMIT_MARKER;
    return result;
  } finally {
    active.delete(value);
  }
};

const fitString = (value: string, maxBytes: number): string => {
  if (byteLength(value) <= maxBytes) return value;
  if (byteLength(EVIDENCE_LIMIT_MARKER) > maxBytes) return "";

  const characters = Array.from(value);
  let low = 0;
  let high = characters.length;
  let best = EVIDENCE_LIMIT_MARKER;
  while (low <= high) {
    const middle = Math.floor((low + high) / 2);
    const candidate = `${characters.slice(0, middle).join("")}${EVIDENCE_LIMIT_MARKER}`;
    if (byteLength(candidate) <= maxBytes) {
      best = candidate;
      low = middle + 1;
    } else {
      high = middle - 1;
    }
  }
  return best;
};

const fitChild = <T>(
  child: T,
  maxBytes: number,
  accepts: (candidate: T) => boolean,
): T | undefined => {
  let low = 0;
  let high = maxBytes;
  let best: T | undefined;
  while (low <= high) {
    const middle = Math.floor((low + high) / 2);
    const candidate = fitValue(child, middle) as T;
    if (accepts(candidate)) {
      best = candidate;
      low = middle + 1;
    } else {
      high = middle - 1;
    }
  }
  return best;
};

const fitArray = (value: readonly unknown[], maxBytes: number): unknown[] => {
  if (byteLength(value) <= maxBytes) return [...value];

  const result: unknown[] = [];
  let omitted = false;
  for (let index = 0; index < value.length; index += 1) {
    const child = fitValue(value[index], maxBytes);
    if (byteLength([...result, child]) <= maxBytes) {
      result.push(child);
      continue;
    }
    const fitted = fitChild(value[index], maxBytes, (candidate) =>
      byteLength([...result, candidate]) <= maxBytes,
    );
    if (fitted !== undefined) result.push(fitted);
    omitted = true;
    break;
  }

  if (omitted) {
    while (result.length > 0 && byteLength([...result, EVIDENCE_LIMIT_MARKER]) > maxBytes) {
      result.pop();
    }
    if (byteLength([...result, EVIDENCE_LIMIT_MARKER]) <= maxBytes) {
      result.push(EVIDENCE_LIMIT_MARKER);
    }
  }
  return result;
};

const fitObject = (value: Record<string, unknown>, maxBytes: number): Record<string, unknown> => {
  if (byteLength(value) <= maxBytes) return { ...value };

  const result: Record<string, unknown> = {};
  let omitted = false;
  for (const key of Object.keys(value)) {
    const child = fitValue(value[key], maxBytes);
    const candidate = { ...result, [key]: child };
    if (byteLength(candidate) <= maxBytes) {
      result[key] = child;
      continue;
    }
    const fitted = fitChild(value[key], maxBytes, (fittedChild) =>
      byteLength({ ...result, [key]: fittedChild }) <= maxBytes,
    );
    if (fitted !== undefined) result[key] = fitted;
    omitted = true;
    break;
  }

  if (omitted) {
    while (
      Object.keys(result).length > 0 &&
      byteLength({ ...result, [TRUNCATION_KEY]: EVIDENCE_LIMIT_MARKER }) > maxBytes
    ) {
      const lastKey = Object.keys(result).at(-1);
      if (lastKey === undefined) break;
      delete result[lastKey];
    }
    if (byteLength({ ...result, [TRUNCATION_KEY]: EVIDENCE_LIMIT_MARKER }) <= maxBytes) {
      result[TRUNCATION_KEY] = EVIDENCE_LIMIT_MARKER;
    }
  }
  return result;
};

const fitValue = (value: unknown, maxBytes: number): unknown => {
  if (byteLength(value) <= maxBytes) {
    if (Array.isArray(value)) return [...value];
    if (value !== null && typeof value === "object") return { ...(value as Record<string, unknown>) };
    return value;
  }
  if (typeof value === "string") return fitString(value, maxBytes);
  if (Array.isArray(value)) return fitArray(value, maxBytes);
  if (value !== null && typeof value === "object") {
    return fitObject(value as Record<string, unknown>, maxBytes);
  }
  return EVIDENCE_LIMIT_MARKER;
};

export const sanitizeEvidenceValue = (value: unknown): unknown =>
  fitValue(projectValue(value, 0, new WeakSet()), EVIDENCE_MAX_BYTES);

export const sanitizeEvidenceRecord = (record: EvidenceRecord): EvidenceRecord => ({
  ...record,
  // Keep request context visible even when a response is independently oversized.
  request: sanitizeEvidenceValue(record.request),
  response: sanitizeEvidenceValue(record.response),
});

export const retainEvidence = (
  records: readonly EvidenceRecord[],
  record: EvidenceRecord,
): readonly EvidenceRecord[] => [
  ...records,
  sanitizeEvidenceRecord(record),
].slice(-EVIDENCE_MAX_RECORDS);
