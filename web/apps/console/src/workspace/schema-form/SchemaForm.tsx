import { useState, type FormEvent } from "react";
import { normalizeSchema, type FieldSource, type SchemaField } from "./schema-field.js";
import { SchemaFieldControl } from "./SchemaFieldControl.js";
import {
  serializeSchemaValues,
  type FieldSources,
  type SchemaSerializationResult,
  type SchemaValueIssue,
} from "./schema-values.js";

export type SchemaFormProps = {
  readonly schema: unknown;
  readonly initialValue?: unknown;
  readonly initialSources?: FieldSources;
  readonly diagnostics?: ReadonlyArray<SchemaValueIssue>;
  readonly onSubmit?: (result: SchemaSerializationResult) => void;
  readonly submitLabel?: string;
  readonly sourceSuggestions?: ReadonlyArray<string>;
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
  if (field.kind === "boolean") return false;
  return "";
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
  sourceField.path.length === 0 ? "root" : sourceField.path.map(String).join(".");

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
  submitLabel = "Save form",
  sourceSuggestions = EMPTY_SUGGESTIONS,
}: SchemaFormProps) => {
  const field = normalizeSchema(schema);
  const [values, setValues] = useState<unknown>(() =>
    initialValue !== undefined ? initialValue : emptyValueFor(field),
  );
  const [sources, setSources] = useState<FieldSources>(() => initialSources);
  const [submitIssues, setSubmitIssues] = useState<ReadonlyArray<SchemaValueIssue>>([]);
  const allDiagnostics = [...diagnostics, ...submitIssues];

  const handleValueChange = (changedField: SchemaField, nextValue: unknown): void => {
    setValues((current: unknown) => setAtPath(current, changedField.path, nextValue));
    const currentSource = sources[sourceKey(changedField)];
    if (currentSource?.mode === "literal") {
      setSources((current) => ({
        ...current,
        [sourceKey(changedField)]: { mode: "literal", value: nextValue },
      }));
    }
  };

  const handleSourceChange = (changedField: SchemaField, source: FieldSource): void => {
    setSources((current) => ({ ...current, [sourceKey(changedField)]: source }));
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    const result = serializeSchemaValues(field, values, sources);
    setSubmitIssues(result.issues);
    onSubmit?.(result);
  };

  return (
    <form className="schema-form" onSubmit={handleSubmit}>
      <SchemaFieldControl
        diagnostics={allDiagnostics}
        field={field}
        onSourceChange={handleSourceChange}
        onValueChange={handleValueChange}
        sourceSuggestions={sourceSuggestions}
        sources={sources}
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
