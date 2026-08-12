import type {
  CapabilityNodeFormValue,
} from "./CapabilityNodeForm.js";
import type { InputBinding, InputPath, LocalInputPath } from "../domain/draft-workspace-models.js";
import type { DraftWorkspace } from "../domain/draft-workspace-models.js";
import type { FieldSources } from "../schema-form/schema-values.js";
import { formatTOMLPath, parseTOMLPath } from "../schema-form/schema-paths.js";

type JsonRecord = Record<string, unknown>;

export type CanonicalCapabilityFormData = {
  readonly capabilityName: string;
  readonly initialValue: Partial<CapabilityNodeFormValue>;
  readonly initialInputValue: unknown;
  readonly initialInputSources: FieldSources;
};

const isRecord = (value: unknown): value is JsonRecord =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const pathParts = (value: unknown): ReadonlyArray<string> | null => {
  if (typeof value === "string") return parseTOMLPath(value);
  if (!isRecord(value) || !Array.isArray(value.parts)) return null;
  if (!value.parts.every((part): part is string => typeof part === "string")) return null;
  return value.parts;
};

const localPath = (value: unknown): string | null => {
  if (typeof value === "string") return value;
  if (!isRecord(value) || value.root !== "local") return null;
  const parts = pathParts(value);
  return parts === null ? null : formatTOMLPath(parts);
};

const sourcePath = (value: unknown): string | null => {
  if (typeof value === "string") return value;
  if (!isRecord(value) || !["input", "state", "context"].includes(String(value.root))) {
    return null;
  }
  const parts = pathParts(value);
  return parts === null ? null : formatTOMLPath([String(value.root), ...parts]);
};

const setPath = (current: unknown, path: string, value: unknown): unknown => {
  const parts = path === "." ? [] : parseTOMLPath(path);
  if (parts === null) return current;
  if (parts.length === 0) return value;
  const [head, ...tail] = parts;
  if (head === undefined) return current;
  if (current === undefined && Number.isInteger(Number(head))) {
    return setPath([], path, value);
  }
  if (Array.isArray(current)) {
    const index = Number(head);
    if (!Number.isInteger(index) || index < 0 || index > current.length) return current;
    const next = [...current];
    next[index] = setPath(next[index], formatTOMLPath(tail), value);
    return next;
  }
  const next = isRecord(current) ? { ...current } : {};
  next[head] = setPath(next[head], formatTOMLPath(tail), value);
  return next;
};

const metadataValue = (step: JsonRecord, key: string): string | number | null | undefined => {
  const value = step[key];
  if (value === null || typeof value === "string" || typeof value === "number") return value;
  return undefined;
};

const localInputPath = (value: unknown): value is LocalInputPath =>
  typeof value === "string" || (
    isRecord(value) &&
    value.root === "local" &&
    Array.isArray(value.parts) &&
    value.parts.every((part): part is string => typeof part === "string")
  );

const inputPath = (value: unknown): value is InputPath =>
  typeof value === "string" || (
    isRecord(value) &&
    (value.root === "input" || value.root === "state" || value.root === "context") &&
    Array.isArray(value.parts) &&
    value.parts.every((part): part is string => typeof part === "string")
  );

const inputBinding = (value: JsonRecord): InputBinding | null => {
  if (!localInputPath(value.target)) return null;
  if (inputPath(value.path)) return { target: value.target, path: value.path };
  if ("value" in value) return { target: value.target, value: value.value };
  return null;
};

const bindingFormData = (
  capabilityName: string,
  inputBindings: ReadonlyArray<InputBinding>,
): Omit<CanonicalCapabilityFormData, "initialValue"> => {
  const initialInputSources: Record<string, FieldSources[string]> = {};
  let initialInputValue: unknown = undefined;
  for (const rawBinding of inputBindings) {
    const target = localPath(rawBinding.target);
    if (target === null) continue;
    if ("path" in rawBinding) {
      const path = sourcePath(rawBinding.path);
      if (path !== null) initialInputSources[target] = { mode: "bind", sourcePath: path };
      continue;
    }
    if ("value" in rawBinding) {
      initialInputValue = setPath(initialInputValue, target, rawBinding.value);
    }
  }
  return {
    capabilityName,
    initialInputValue,
    initialInputSources,
  };
};

const formDataFromValue = (
  input: CapabilityNodeFormValue,
): CanonicalCapabilityFormData => ({
  ...bindingFormData(input.capabilityName, input.inputBindings ?? []),
  initialValue: input,
});

const formDataFromBindings = (
  capabilityName: string,
  inputBindings: ReadonlyArray<InputBinding>,
  initialValue: Partial<CapabilityNodeFormValue>,
): CanonicalCapabilityFormData => {
  return { ...bindingFormData(capabilityName, inputBindings), initialValue };
};

export const capabilityFormDataFromValue = (
  input: CapabilityNodeFormValue,
): CanonicalCapabilityFormData => formDataFromValue(input);

export const canonicalCapabilityFormData = (
  draft: DraftWorkspace,
  stepId: string,
): CanonicalCapabilityFormData | null => {
  const steps = isRecord(draft.draft) ? draft.draft.steps : undefined;
  if (!isRecord(steps) || !isRecord(steps[stepId])) return null;
  const step = steps[stepId];
  const capabilityName = step.use;
  if (typeof capabilityName !== "string" || capabilityName.trim() === "") return null;

  const description = metadataValue(step, "desc");
  const retry = metadataValue(step, "retry");
  const timeoutSeconds = metadataValue(step, "timeout_seconds");
  const initialValue = {
    stepId,
    ...(typeof description === "string" || description === null ? { description } : {}),
    ...(typeof retry === "number" || retry === null ? { retry } : {}),
    ...(typeof timeoutSeconds === "number" || timeoutSeconds === null
      ? { timeoutSeconds }
      : {}),
  } satisfies Partial<CapabilityNodeFormValue>;
  const inputBindings: InputBinding[] = [];
  const input = step.input;
  if (Array.isArray(input)) {
    for (const rawBinding of input) {
      if (!isRecord(rawBinding)) continue;
      const binding = inputBinding(rawBinding);
      if (binding !== null) inputBindings.push(binding);
    }
  }

  return formDataFromBindings(capabilityName, inputBindings, { ...initialValue, stepId });
};
