import type {
  DraftDiagnostic,
  DraftWorkspace,
  InputBinding,
  InputPath,
  LocalInputPath,
  OutputBinding,
  StatePath,
} from "../domain/draft-workspace-models.js";
import { formatTOMLPath, parseTOMLPath } from "../schema-form/schema-paths.js";
import { normalizeSchema, type SchemaField } from "../schema-form/schema-field.js";

type JsonRecord = Record<string, unknown>;

export type JsonValue =
  | null
  | boolean
  | number
  | string
  | ReadonlyArray<JsonValue>
  | { readonly [key: string]: JsonValue };

const isRecord = (value: unknown): value is JsonRecord =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const hasOwn = (value: JsonRecord, key: string): boolean =>
  Object.prototype.hasOwnProperty.call(value, key);

const hasExactKeys = (value: JsonRecord, keys: ReadonlyArray<string>): boolean => {
  const actual = Reflect.ownKeys(value);
  return actual.length === keys.length && keys.every((key) => actual.includes(key));
};

/** Guard the recursive JSON subset used by literal input bindings. */
export const isJsonValue = (value: unknown): value is JsonValue => {
  if (value === null || typeof value === "boolean" || typeof value === "string") return true;
  if (typeof value === "number") return Number.isFinite(value);
  if (Array.isArray(value)) {
    if (Object.getOwnPropertySymbols(value).length > 0) return false;
    for (const item of value) {
      if (!isJsonValue(item)) return false;
    }
    return Object.keys(value).every((key) => /^(0|[1-9]\d*)$/.test(key));
  }
  if (!isRecord(value)) return false;
  if (Object.getPrototypeOf(value) !== Object.prototype && Object.getPrototypeOf(value) !== null) return false;
  if (Object.getOwnPropertySymbols(value).length > 0) return false;
  return Object.values(value).every(isJsonValue);
};

const stringParts = (value: unknown): string[] | null => {
  if (!Array.isArray(value)) return null;
  const parts: string[] = [];
  for (const part of value) {
    if (typeof part !== "string") return null;
    parts.push(part);
  }
  return parts;
};

const validPathParts = (parts: ReadonlyArray<string>): boolean => {
  if (parts.some((part) => part.length === 0)) return false;
  const formatted = formatTOMLPath(parts);
  return parseTOMLPath(formatted) !== null;
};

const localPathParts = (value: unknown): string[] | null => {
  if (typeof value === "string") {
    const parts = parseTOMLPath(value);
    return parts === null ? null : [...parts];
  }
  if (!isRecord(value) || value.root !== "local") return null;
  if (!hasExactKeys(value, ["root", "parts"])) return null;
  const parts = stringParts(value.parts);
  return parts !== null && validPathParts(parts) ? parts : null;
};

const inputPathParts = (value: unknown): string[] | null => {
  if (typeof value === "string") {
    const parts = parseTOMLPath(value);
    return parts !== null &&
      parts.length > 0 &&
      (parts[0] === "input" || parts[0] === "state" || parts[0] === "context")
      ? [...parts]
      : null;
  }
  if (!isRecord(value)) return null;
  if (value.root !== "input" && value.root !== "state" && value.root !== "context") return null;
  if (!hasExactKeys(value, ["root", "parts"])) return null;
  const parts = stringParts(value.parts);
  return parts !== null && validPathParts(parts) ? [value.root, ...parts] : null;
};

const statePathParts = (value: unknown): string[] | null => {
  if (typeof value === "string") {
    const parts = parseTOMLPath(value);
    return parts !== null && parts.length > 1 && parts[0] === "state" ? [...parts] : null;
  }
  if (!isRecord(value) || value.root !== "state") return null;
  if (!hasExactKeys(value, ["root", "parts"])) return null;
  const parts = stringParts(value.parts);
  return parts !== null && parts.length > 0 && validPathParts(parts) ? ["state", ...parts] : null;
};

const inputPath = (value: unknown): InputPath | null => {
  const parts = inputPathParts(value);
  if (parts === null) return null;
  if (typeof value === "string") return value;
  if (!isRecord(value)) return null;
  const root = value.root;
  if (root !== "input" && root !== "state" && root !== "context") return null;
  return { root, parts: parts.slice(1) };
};

const localPath = (value: unknown): LocalInputPath | null => {
  const parts = localPathParts(value);
  if (parts === null) return null;
  if (typeof value === "string") return value;
  return { root: "local", parts: [...parts] };
};

const statePath = (value: unknown): StatePath | null => {
  const parts = statePathParts(value);
  if (parts === null) return null;
  if (typeof value === "string") return value;
  return { root: "state", parts: parts.slice(1) };
};

const canonicalLocalPath = (value: unknown): string | null => {
  const parts = localPathParts(value);
  return parts === null ? null : formatTOMLPath(parts);
};

const canonicalInputPath = (value: unknown): string | null => {
  const parts = inputPathParts(value);
  return parts === null ? null : formatTOMLPath(parts);
};

const canonicalStatePath = (value: unknown): string | null => {
  const parts = statePathParts(value);
  return parts === null ? null : formatTOMLPath(parts);
};

const parsedInputBinding = (value: unknown): InputBinding | null => {
  if (!isRecord(value)) return null;
  const target = localPath(value.target);
  if (target === null) return null;
  const hasPath = hasOwn(value, "path");
  const hasValue = hasOwn(value, "value");
  if (hasPath === hasValue) return null;
  if (hasPath) {
    if (!hasExactKeys(value, ["path", "target"])) return null;
    const path = inputPath(value.path);
    return path === null ? null : { path, target };
  }
  if (!hasExactKeys(value, ["target", "value"])) return null;
  return !isJsonValue(value.value) ? null : { target, value: value.value };
};

const parsedOutputBinding = (value: unknown): OutputBinding | null => {
  if (!isRecord(value)) return null;
  if (!hasExactKeys(value, ["source", "target"])) return null;
  const source = localPath(value.source);
  const target = statePath(value.target);
  return source === null || target === null ? null : { source, target };
};

const unsupportedReason = (field: "input" | "output", index: number): string =>
  `Unsupported ${field} binding at index ${index}: the row is not a canonical ${field} binding.`;

type ParsedRows<T> = {
  readonly values: ReadonlyArray<T>;
  readonly unsupported: ReadonlyArray<UnsupportedBindingRow>;
};

const parseRows = <T>(
  field: "input" | "output",
  raw: unknown,
  parse: (value: unknown) => T | null,
): ParsedRows<T> => {
  const values: T[] = [];
  const unsupported: UnsupportedBindingRow[] = [];
  if (raw !== undefined && !Array.isArray(raw)) {
    return {
      values,
      unsupported: [{ field, index: 0, raw, reason: unsupportedReason(field, 0) }],
    };
  }
  const rows = raw === undefined ? [] : raw;
  rows.forEach((value, index) => {
    const parsed = parse(value);
    if (parsed === null) {
      unsupported.push({ field, index, raw: value, reason: unsupportedReason(field, index) });
    } else {
      values.push(parsed);
    }
  });
  return { values, unsupported };
};

type SelectedStepRecord = {
  readonly step: JsonRecord;
  readonly compiledNodeIndex: number | null;
};

const stepFromDraft = (draft: DraftWorkspace, stepId: string): SelectedStepRecord | null => {
  if (!isRecord(draft.draft)) return null;
  if (Array.isArray(draft.draft.nodes)) {
    for (const [index, node] of draft.draft.nodes.entries()) {
      if (isRecord(node) && node.id === stepId) return { step: node, compiledNodeIndex: index };
    }
    return null;
  }
  const steps = draft.draft.steps;
  if (!isRecord(steps) || !isRecord(steps[stepId])) return null;
  return { step: steps[stepId], compiledNodeIndex: null };
};

/** Compound canonical projection used by the selected-step setup, input, and output forms. */
export type SelectedStepDataflow = {
  readonly stepId: string;
  readonly compiledNodeIndex: number | null;
  readonly capabilityName: string;
  readonly description: string | null | undefined;
  readonly retry: number | null | undefined;
  readonly timeoutSeconds: number | null | undefined;
  readonly inputs: ReadonlyArray<InputBinding>;
  readonly outputs: ReadonlyArray<OutputBinding>;
  readonly unsupported: ReadonlyArray<UnsupportedBindingRow>;
};

export type UnsupportedBindingRow = {
  readonly field: "input" | "output";
  readonly index: number;
  readonly raw: unknown;
  readonly reason: string;
};

export type CapabilitySetupPatch = {
  readonly description?: string | null;
  readonly retry?: number | null;
  readonly timeoutSeconds?: number | null;
};

export type BindingRow<T> =
  | { readonly kind: "canonical"; readonly index: number; readonly value: T }
  | UnsupportedBindingRow & { readonly kind: "unsupported" };

export type InputBindingRow = BindingRow<InputBinding>;
export type OutputBindingRow = BindingRow<OutputBinding>;

export const projectSelectedStepDataflow = (
  draft: DraftWorkspace,
  stepId: string,
): SelectedStepDataflow | null => {
  const selected = stepFromDraft(draft, stepId);
  if (selected === null) return null;
  const { step, compiledNodeIndex } = selected;
  const capabilityName = typeof step.use === "string" ? step.use : step.node;
  if (typeof capabilityName !== "string" || capabilityName.length === 0) return null;
  const inputs = parseRows("input", step.input, parsedInputBinding);
  const outputs = parseRows("output", step.output, parsedOutputBinding);
  const description = step.desc === null || typeof step.desc === "string" ? step.desc : undefined;
  const retry = step.retry === null || typeof step.retry === "number" ? step.retry : undefined;
  const timeoutSeconds =
    step.timeout_seconds === null || typeof step.timeout_seconds === "number"
      ? step.timeout_seconds
      : undefined;
  return {
    stepId,
    compiledNodeIndex,
    capabilityName,
    description,
    retry,
    timeoutSeconds,
    inputs: inputs.values,
    outputs: outputs.values,
    unsupported: [...inputs.unsupported, ...outputs.unsupported],
  };
};

const rowsFor = <T>(
  raw: unknown,
  parse: (value: unknown) => T | null,
  field: "input" | "output",
): ReadonlyArray<BindingRow<T>> => {
  const rows: Array<BindingRow<T>> = [];
  if (raw !== undefined && !Array.isArray(raw)) {
    return [{ kind: "unsupported", field, index: 0, raw, reason: unsupportedReason(field, 0) }];
  }
  const values = raw === undefined ? [] : raw;
  values.forEach((value, index) => {
    const parsed = parse(value);
    if (parsed === null) {
      rows.push({ kind: "unsupported", field, index, raw: value, reason: unsupportedReason(field, index) });
    } else {
      rows.push({ kind: "canonical", index, value: parsed });
    }
  });
  return rows;
};

export const inputBindingRows = (raw: unknown): ReadonlyArray<InputBindingRow> =>
  rowsFor(raw, parsedInputBinding, "input");

export const outputBindingRows = (raw: unknown): ReadonlyArray<OutputBindingRow> =>
  rowsFor(raw, parsedOutputBinding, "output");

export const serializeInputBindingRow = (value: unknown): InputBinding | null => {
  if (!isRecord(value)) return null;
  const target = canonicalLocalPath(value.target);
  if (target === null) return null;
  if (hasOwn(value, "path") && !hasOwn(value, "value")) {
    if (!hasExactKeys(value, ["path", "target"])) return null;
    const path = canonicalInputPath(value.path);
    return path === null ? null : { path, target };
  }
  if (!hasOwn(value, "path") && hasOwn(value, "value") && isJsonValue(value.value)) {
    if (!hasExactKeys(value, ["target", "value"])) return null;
    return { target, value: value.value };
  }
  return null;
};

export const serializeInputBindingRows = (
  rows: ReadonlyArray<InputBindingRow>,
): ReadonlyArray<InputBinding> | null => {
  const bindings: InputBinding[] = [];
  for (const row of rows) {
    if (row.kind === "unsupported") return null;
    const binding = serializeInputBindingRow(row.value);
    if (binding === null) return null;
    bindings.push(binding);
  }
  return bindings;
};

export const serializeOutputBindingRow = (value: unknown): OutputBinding | null => {
  if (!isRecord(value)) return null;
  if (!hasExactKeys(value, ["source", "target"])) return null;
  const source = canonicalLocalPath(value.source);
  const target = canonicalStatePath(value.target);
  return source === null || target === null ? null : { source, target };
};

export const serializeOutputBindingRows = (
  rows: ReadonlyArray<OutputBindingRow>,
): ReadonlyArray<OutputBinding> | null => {
  const bindings: OutputBinding[] = [];
  for (const row of rows) {
    if (row.kind === "unsupported") return null;
    const binding = serializeOutputBindingRow(row.value);
    if (binding === null) return null;
    bindings.push(binding);
  }
  return bindings;
};

const descendantPaths = (field: SchemaField): ReadonlyArray<ReadonlyArray<string | number>> => {
  const paths: Array<ReadonlyArray<string | number>> = [];
  for (const child of field.children) {
    paths.push(child.path, ...descendantPaths(child));
  }
  if (field.item !== null) paths.push(field.item.path, ...descendantPaths(field.item));
  return paths;
};

const schemaPathStrings = (schema: unknown): ReadonlyArray<string> => {
  const field = normalizeSchema(schema);
  return descendantPaths(field).map((path) => formatTOMLPath(path));
};

const prefixedSchemaPaths = (prefix: string, schema: unknown): ReadonlyArray<string> =>
  schemaPathStrings(schema).flatMap((path) => {
    const parts = parseTOMLPath(path);
    return parts === null ? [] : [formatTOMLPath([prefix, ...parts])];
  });

export const workflowSourceSuggestions = (
  inputSchema: unknown,
  stateSchema: unknown,
): ReadonlyArray<string> => [
  ...prefixedSchemaPaths("input", inputSchema),
  ...prefixedSchemaPaths("state", stateSchema),
];

export const capabilityLocalPathSuggestions = (capabilitySchema: unknown): ReadonlyArray<string> => [
  ".",
  ...schemaPathStrings(capabilitySchema),
];

export const stateTargetSuggestions = (stateSchema: unknown): ReadonlyArray<string> =>
  prefixedSchemaPaths("state", stateSchema);

const schemaAtPath = (schema: unknown, parts: ReadonlyArray<string>): unknown | null => {
  let current: unknown = schema;
  for (const part of parts) {
    if (!isRecord(current)) return null;
    if (current.type === "object" && isRecord(current.properties)) {
      current = current.properties[part];
      continue;
    }
    if (
      current.type === "array" &&
      current.items !== undefined &&
      /^(0|[1-9]\d*)$/.test(part) &&
      Number.isSafeInteger(Number(part))
    ) {
      current = current.items;
      continue;
    }
    return null;
  }
  return current === undefined ? null : current;
};

export const inferredStateSchemaPreview = (
  outputSchema: unknown,
  source: LocalInputPath,
  target: StatePath,
): unknown | null => {
  if (statePathParts(target) === null) return null;
  const sourceParts = localPathParts(source);
  if (sourceParts === null) return null;
  return schemaAtPath(outputSchema, sourceParts);
};

export type BindingDiagnostics = {
  readonly rowIssues: Readonly<Record<number, ReadonlyArray<DraftDiagnostic>>>;
  readonly unmatchedIssues: ReadonlyArray<DraftDiagnostic>;
};

type RowLocation = { readonly field: "input" | "output"; readonly index: number };
type PointerLocation = RowLocation & { readonly stepId: string };

const nodeLocation = (path: string): { readonly index: number; readonly field: "input" | "output"; readonly bindingIndex: number } | null => {
  const match = /^nodes\[(\d+)\]\.(input|output)\[(\d+)\](?:\.|$)/.exec(path);
  if (match === null) return null;
  const nodeIndex = Number(match[1]);
  const bindingIndex = Number(match[3]);
  return Number.isInteger(nodeIndex) && Number.isInteger(bindingIndex)
    ? { index: nodeIndex, field: match[2] === "input" ? "input" : "output", bindingIndex }
    : null;
};

const decodePointerSegment = (segment: string): string | null => {
  let decoded = "";
  for (let index = 0; index < segment.length; index++) {
    const character = segment[index];
    if (character !== "~") {
      decoded += character;
      continue;
    }
    const escape = segment[index + 1];
    if (escape !== "0" && escape !== "1") return null;
    decoded += escape === "0" ? "~" : "/";
    index++;
  }
  return decoded;
};

const pointerLocation = (path: string): PointerLocation | null => {
  if (!path.startsWith("/")) return null;
  const parts: string[] = [];
  for (const rawPart of path.split("/").slice(1)) {
    const part = decodePointerSegment(rawPart);
    if (part === null) return null;
    parts.push(part);
  }
  const field = parts[2];
  const index = parts[3];
  if (parts[0] !== "steps" || (field !== "input" && field !== "output") || index === undefined || !/^\d+$/.test(index)) return null;
  const stepId = parts[1];
  return stepId === undefined ? null : { field, index: Number(index), stepId };
};

const focusedLocation = (
  path: string,
  diagnostic: DraftDiagnostic,
  stepId: string,
  field: "input" | "output",
): RowLocation | null => {
  if (diagnostic.stepId !== stepId) return null;
  const match = /^bindings\[(\d+)\](?:\.|$)/.exec(path);
  return match === null ? null : { field, index: Number(match[1]) };
};

export const bindingDiagnosticsForStep = (
  diagnostics: ReadonlyArray<DraftDiagnostic>,
  stepId: string,
  field: "input" | "output",
  compiledNodeIndex: number | null,
): BindingDiagnostics => {
  const rowIssues: Record<number, DraftDiagnostic[]> = {};
  const unmatchedIssues: DraftDiagnostic[] = [];
  for (const diagnostic of diagnostics) {
    if (diagnostic.stepId !== null && diagnostic.stepId !== stepId) {
      unmatchedIssues.push(diagnostic);
      continue;
    }
    const node = nodeLocation(diagnostic.path);
    const pointer = pointerLocation(diagnostic.path);
    const focused = focusedLocation(diagnostic.path, diagnostic, stepId, field);
    const location = node !== null && compiledNodeIndex !== null && node.index === compiledNodeIndex && node.field === field
      ? { field: node.field, index: node.bindingIndex }
      : pointer !== null && pointer.field === field && pointer.stepId === stepId
        ? pointer
        : focused !== null
          ? focused
          : null;
    if (location === null) {
      unmatchedIssues.push(diagnostic);
      continue;
    }
    const existing = rowIssues[location.index] ?? [];
    rowIssues[location.index] = [...existing, diagnostic];
  }
  return { rowIssues, unmatchedIssues };
};
