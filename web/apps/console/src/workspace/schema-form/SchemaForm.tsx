import { useState, type FormEvent, type ReactNode } from "react";
import { normalizeSchema, type FieldSource, type SchemaField } from "./schema-field.js";
import { SchemaFieldControl } from "./SchemaFieldControl.js";
import {
  rebaseFieldSourcesAfterArrayRemoval,
  rebaseSchemaIssuesAfterArrayRemoval,
  serializeSchemaValues,
  type FieldSources,
  type SchemaSerializationResult,
  type SchemaValueIssue,
} from "./schema-values.js";
import { formatTOMLPath } from "./schema-paths.js";

export type SchemaFormProps = {
  readonly schema: unknown;
  readonly initialValue?: unknown;
  readonly initialSources?: FieldSources;
  readonly diagnostics?: ReadonlyArray<SchemaValueIssue>;
  readonly onSubmit?: (result: SchemaSerializationResult) => void;
  readonly onValueChange?: (result: SchemaSerializationResult) => void;
  readonly onDirtyChange?: (dirty: boolean) => void;
  readonly renderBeforeFields?: ReactNode;
  readonly submitLabel?: string;
  readonly sourceSuggestions?: ReadonlyArray<string>;
  readonly showSourceControls?: boolean;
};

const EMPTY_SOURCES: FieldSources = {};
const EMPTY_DIAGNOSTICS: ReadonlyArray<SchemaValueIssue> = [];
const EMPTY_SUGGESTIONS: ReadonlyArray<string> = [];

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const emptyValueFor = (field: SchemaField): unknown => {
  if (field.hasDefault) return field.defaultValue;
  if (field.kind === "object") return {};
  if (field.kind === "array") return [];
  if (field.kind === "boolean") return undefined;
  if (field.kind === "json") return undefined;
  return "";
};

const readAtPath = (
  current: unknown,
  path: ReadonlyArray<string | number>,
): unknown => {
  let value = current;
  for (const part of path) {
    if (Array.isArray(value)) {
      const index = typeof part === "number" ? part : Number(part);
      if (!Number.isInteger(index)) return undefined;
      value = value[index];
    } else if (isRecord(value) && typeof part === "string") {
      value = value[part];
    } else {
      return undefined;
    }
  }
  return value;
};

const setAtPath = (
  current: unknown,
  path: ReadonlyArray<string | number>,
  value: unknown,
): unknown => {
  if (path.length === 0) return value;
  const [head, ...tail] = path;
  if (typeof head === "number" || Array.isArray(current)) {
    const index = Number(head);
    const next = Array.isArray(current) ? current : [];
    const child = setAtPath(next[index], tail, value);
    return Array.from(
      { length: Math.max(next.length, index + 1) },
      (_, itemIndex) => (itemIndex === index ? child : next[itemIndex]),
    );
  }
  const next = isRecord(current) ? { ...current } : {};
  const key = String(head);
  return { ...next, [key]: setAtPath(next[key], tail, value) };
};

const sourceKey = (sourceField: SchemaField): string =>
  formatTOMLPath(sourceField.path);

const rawSchemaText = (schema: unknown): string => {
  try {
    const encoded = JSON.stringify(schema, null, 2);
    return encoded ?? "";
  } catch {
    return "The schema could not be displayed as JSON.";
  }
};

export const SchemaForm = ({
  schema,
  initialValue,
  initialSources = EMPTY_SOURCES,
  diagnostics = EMPTY_DIAGNOSTICS,
  onSubmit,
  onValueChange,
  onDirtyChange,
  renderBeforeFields,
  submitLabel = "Save form",
  sourceSuggestions = EMPTY_SUGGESTIONS,
  showSourceControls = true,
}: SchemaFormProps) => {
  const field = normalizeSchema(schema);
  const [values, setValues] = useState<unknown>(() =>
    initialValue !== undefined ? initialValue : emptyValueFor(field),
  );
  const [sources, setSources] = useState<FieldSources>(() => initialSources);
  const [submitIssues, setSubmitIssues] = useState<ReadonlyArray<SchemaValueIssue>>([]);
  const allDiagnostics = [...diagnostics, ...submitIssues];

  const handleValueChange = (changedField: SchemaField, nextValue: unknown): void => {
    const nextValues = setAtPath(values, changedField.path, nextValue);
    let nextSources = sources;
    setValues(nextValues);
    onDirtyChange?.(true);
    const currentSource = sources[sourceKey(changedField)];
    if (currentSource?.mode === "literal") {
      nextSources = {
        ...sources,
        [sourceKey(changedField)]: { mode: "literal", value: nextValue },
      };
      setSources(() => ({
        ...sources,
        [sourceKey(changedField)]: { mode: "literal", value: nextValue },
      }));
    }
    onValueChange?.(serializeSchemaValues(field, nextValues, nextSources));
  };

  const handleSourceChange = (changedField: SchemaField, source: FieldSource): void => {
    onDirtyChange?.(true);
    const nextValues = source.mode === "literal"
      ? setAtPath(values, changedField.path, source.value)
      : values;
    const nextSources = { ...sources, [sourceKey(changedField)]: source };
    if (source.mode === "literal") {
      setValues(nextValues);
    }
    setSources(nextSources);
    onValueChange?.(serializeSchemaValues(field, nextValues, nextSources));
  };

  const handleArrayItemRemove = (arrayField: SchemaField, index: number): void => {
    onDirtyChange?.(true);
    const arrayValue = readAtPath(values, arrayField.path);
    if (!Array.isArray(arrayValue)) return;
    const nextValues = setAtPath(
      values,
      arrayField.path,
      arrayValue.filter((_, itemIndex) => itemIndex !== index),
    );
    const nextSources = rebaseFieldSourcesAfterArrayRemoval(sources, arrayField.path, index);
    const nextIssues = rebaseSchemaIssuesAfterArrayRemoval(submitIssues, arrayField.path, index);
    setValues(nextValues);
    setSources(nextSources);
    setSubmitIssues(nextIssues);
    onValueChange?.(serializeSchemaValues(field, nextValues, nextSources));
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    const result = serializeSchemaValues(field, values, sources);
    setSubmitIssues(result.issues);
    onSubmit?.(result);
  };

  return (
    <form className="schema-form" noValidate onSubmit={handleSubmit}>
      {renderBeforeFields}
      <SchemaFieldControl
        diagnostics={allDiagnostics}
        field={field}
        onArrayItemRemove={handleArrayItemRemove}
        onSourceChange={handleSourceChange}
        onValueChange={handleValueChange}
        sourceSuggestions={sourceSuggestions}
        sources={sources}
        showSourceControl={showSourceControls}
        value={values}
      />
      <button type="submit">{submitLabel}</button>
      <details className="schema-form__raw">
        <summary>Raw schema</summary>
        <pre aria-label="Raw schema JSON" role="region" tabIndex={0}>{rawSchemaText(schema)}</pre>
      </details>
    </form>
  );
};
