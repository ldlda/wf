import { useRef, useState, type FormEvent } from "react";
import type { DraftDiagnostic, InputBinding } from "../domain/draft-workspace-models.js";
import { SchemaFieldControl } from "../schema-form/SchemaFieldControl.js";
import { formatTOMLPath, parseGraphSourcePath, parseTOMLPath } from "../schema-form/schema-paths.js";
import {
  normalizeSchema,
  schemaFieldAtPath,
  type FieldSource,
  type SchemaField,
} from "../schema-form/schema-field.js";
import { serializeSchemaValues, type FieldSources } from "../schema-form/schema-values.js";
import { formatBoundedJson } from "./format-bounded-json.js";
import {
  inputBindingRows,
  isJsonValue,
  serializeInputBindingRow,
  type InputBindingRow,
} from "./selected-step-dataflow.js";

type EditableRow = {
  readonly kind: "canonical";
  readonly id: string;
  readonly rawIndex: number;
  readonly target: string;
  readonly mode: "path" | "literal";
  readonly sourcePath: string;
  readonly value: unknown;
  readonly jsonText: string | null;
};

type UnsupportedRow = Extract<InputBindingRow, { readonly kind: "unsupported" }> & {
  readonly id: string;
};

type FormRow = EditableRow | UnsupportedRow;

export type StepInputBindingsFormProps = {
  readonly inputSchema: unknown;
  readonly initialRows?: ReadonlyArray<InputBindingRow>;
  readonly initialBindings?: ReadonlyArray<InputBinding>;
  readonly rowDiagnostics?: Readonly<Record<number, ReadonlyArray<DraftDiagnostic>>>;
  readonly onSubmit: (bindings: ReadonlyArray<InputBinding>) => void | Promise<void>;
  readonly onDirtyChange?: (dirty: boolean) => void;
  readonly submitLabel?: string;
};

const EMPTY_ROWS: ReadonlyArray<InputBindingRow> = [];
const EMPTY_DIAGNOSTICS: Readonly<Record<number, ReadonlyArray<DraftDiagnostic>>> = {};

const pathText = (
  value: string | { readonly parts: ReadonlyArray<string>; readonly root: string },
): string => typeof value === "string" ? value : formatTOMLPath([value.root, ...value.parts]);

const jsonText = (value: unknown): string => {
  const encoded = JSON.stringify(value, null, 2);
  return encoded ?? "";
};

const rowsFrom = (rows: ReadonlyArray<InputBindingRow>): ReadonlyArray<FormRow> => rows.map((row, index) => {
  if (row.kind === "unsupported") return { ...row, id: `input-row-${index}` };
  if ("path" in row.value) {
    return {
      kind: "canonical",
      id: `input-row-${index}`,
      rawIndex: row.index,
      target: pathText(row.value.target),
      mode: "path",
      sourcePath: pathText(row.value.path),
      value: null,
      jsonText: null,
    };
  }
  return {
    kind: "canonical",
    id: `input-row-${index}`,
    rawIndex: row.index,
    target: pathText(row.value.target),
    mode: "literal",
    sourcePath: "input.",
    value: row.value.value,
    jsonText: null,
  };
});

const inputRows = (
  initialRows: ReadonlyArray<InputBindingRow> | undefined,
  initialBindings: ReadonlyArray<InputBinding> | undefined,
): ReadonlyArray<InputBindingRow> => {
  if (initialRows !== undefined) return initialRows;
  return initialBindings === undefined ? EMPTY_ROWS : inputBindingRows(initialBindings);
};

const updateRow = (
  rows: ReadonlyArray<FormRow>,
  id: string,
  update: (row: EditableRow) => EditableRow,
): ReadonlyArray<FormRow> => rows.map((row) =>
  row.kind === "canonical" && row.id === id ? update(row) : row,
);

const rowIssueMessages = (
  row: EditableRow,
  rowDiagnostics: Readonly<Record<number, ReadonlyArray<DraftDiagnostic>>>,
  localIssues: Readonly<Record<string, ReadonlyArray<string>>>,
): ReadonlyArray<string> => [
  ...(rowDiagnostics[row.rawIndex] ?? []).map((diagnostic) => diagnostic.message),
  ...(localIssues[row.id] ?? []),
];

const literalValueFor = (
  field: SchemaField | null,
  row: EditableRow,
): { readonly value: unknown; readonly issues: ReadonlyArray<string> } => {
  if (field === null) {
    const raw = row.jsonText ?? jsonText(row.value);
    try {
      const parsed: unknown = JSON.parse(raw);
      return isJsonValue(parsed)
        ? { value: parsed, issues: [] }
        : { value: parsed, issues: ["Literal value must be valid JSON."] };
    } catch {
      return { value: raw, issues: ["Literal value must be valid JSON."] };
    }
  }
  const result = serializeSchemaValues(field, row.value, {
    [formatTOMLPath(field.path)]: { mode: "literal", value: row.value },
  });
  return {
    value: result.value,
    issues: result.issues.map((issue) => issue.message),
  };
};

const bindingForRow = (
  root: SchemaField,
  row: EditableRow,
): { readonly binding: InputBinding | null; readonly issues: ReadonlyArray<string> } => {
  const target = row.target.trim();
  if (target === "") return { binding: null, issues: ["Target is required."] };
  if (row.mode === "path") {
    if (parseGraphSourcePath(row.sourcePath) === null) {
      return { binding: null, issues: ["Source path must start with input., state., or context."] };
    }
    const binding = serializeInputBindingRow({ target, path: row.sourcePath });
    return binding === null
      ? { binding: null, issues: ["Enter a valid target and source path."] }
      : { binding, issues: [] };
  }
  const targetParts = parseTOMLPath(target);
  const field = targetParts === null
    ? null
    : schemaFieldAtPath(root, targetParts.map((part) => /^\d+$/.test(part) ? Number(part) : part));
  const literal = literalValueFor(field, row);
  if (literal.issues.length > 0) return { binding: null, issues: literal.issues };
  const binding = serializeInputBindingRow({ target, value: literal.value });
  return binding === null
    ? { binding: null, issues: ["Enter a valid target and JSON literal."] }
    : { binding, issues: [] };
};

const sourceForRow = (field: SchemaField, row: EditableRow): FieldSources => ({
  [formatTOMLPath(field.path)]: row.mode === "path"
    ? { mode: "bind", sourcePath: row.sourcePath }
    : { mode: "literal", value: row.value },
});

export const StepInputBindingsForm = ({
  inputSchema,
  initialRows,
  initialBindings,
  rowDiagnostics = EMPTY_DIAGNOSTICS,
  onSubmit,
  onDirtyChange,
  submitLabel = "Save inputs",
}: StepInputBindingsFormProps) => {
  const root = normalizeSchema(inputSchema);
  const [rows, setRows] = useState<ReadonlyArray<FormRow>>(() =>
    rowsFrom(inputRows(initialRows, initialBindings)),
  );
  const [localIssues, setLocalIssues] = useState<Readonly<Record<string, ReadonlyArray<string>>>>({});
  const nextId = useRef(rows.length);

  const markDirty = (): void => onDirtyChange?.(true);

  const editRow = (id: string, update: (row: EditableRow) => EditableRow): void => {
    setRows((current) => updateRow(current, id, update));
    markDirty();
  };

  const moveRow = (index: number, direction: -1 | 1): void => {
    setRows((current) => {
      const nextIndex = index + direction;
      if (nextIndex < 0 || nextIndex >= current.length) return current;
      const next = [...current];
      const currentRow = next[index];
      const replacement = next[nextIndex];
      if (currentRow === undefined || replacement === undefined) return current;
      next[index] = replacement;
      next[nextIndex] = currentRow;
      return next;
    });
    markDirty();
  };

  const removeRow = (id: string): void => {
    setRows((current) => current.filter((row) => row.id !== id));
    markDirty();
  };

  const addRow = (): void => {
    const id = `input-row-${nextId.current++}`;
    setRows((current) => [
      ...current,
      {
        kind: "canonical",
        id,
        rawIndex: -1,
        target: "",
        mode: "path",
        sourcePath: "input.",
        value: null,
        jsonText: null,
      },
    ]);
    markDirty();
  };

  const submit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    const nextIssues: Record<string, ReadonlyArray<string>> = {};
    const bindings: InputBinding[] = [];
    for (const row of rows) {
      if (row.kind === "unsupported") {
        nextIssues[row.id] = ["Remove or repair this unsupported input row before saving."];
        continue;
      }
      const result = bindingForRow(root, row);
      if (result.binding === null) nextIssues[row.id] = result.issues;
      else bindings.push(result.binding);
    }
    setLocalIssues(nextIssues);
    if (Object.keys(nextIssues).length > 0) return;
    void Promise.resolve(onSubmit(bindings)).catch(() => undefined);
  };

  const clear = (): void => {
    setLocalIssues({});
    markDirty();
    void Promise.resolve(onSubmit([])).catch(() => undefined);
  };

  return (
    <form className="schema-form authoring-form" noValidate onSubmit={submit}>
      <div className="schema-form__group">
        {rows.length === 0 && <p>No input bindings configured.</p>}
        {rows.map((row, index) => {
          const rowNumber = index + 1;
          if (row.kind === "unsupported") {
            const unsupportedIssues = [
              ...(rowDiagnostics[row.index] ?? []).map((diagnostic) => diagnostic.message),
              ...(localIssues[row.id] ?? []),
            ];
            return (
              <fieldset aria-label={`Unsupported input row ${rowNumber}`} className="schema-form__group" key={row.id}>
                <legend>Input row {rowNumber}: unsupported</legend>
                <p className="schema-form__fallback-reason">{row.reason}</p>
                <details className="schema-form__raw" open>
                  <summary>Raw unsupported input</summary>
                  <pre aria-label={`Raw unsupported input row ${rowNumber}`} role="region" tabIndex={0}>
                    {formatBoundedJson(row.raw)}
                  </pre>
                </details>
                {unsupportedIssues.length > 0 && (
                  <div className="schema-form__diagnostics" role="alert">
                    {unsupportedIssues.map((issue) => <p key={issue}>{issue}</p>)}
                  </div>
                )}
                <button
                  aria-label={`Remove unsupported input row ${rowNumber}`}
                  className="schema-form__secondary-action"
                  onClick={() => removeRow(row.id)}
                  type="button"
                >
                  Remove to repair
                </button>
              </fieldset>
            );
          }
          const targetParts = parseTOMLPath(row.target.trim());
          const field = targetParts === null
            ? null
            : schemaFieldAtPath(root, targetParts.map((part) => /^\d+$/.test(part) ? Number(part) : part));
          const issues = rowIssueMessages(row, rowDiagnostics, localIssues);
          const source = field === null ? null : sourceForRow(field, row);
          return (
            <fieldset aria-label={`Input row ${rowNumber}`} className="schema-form__group" key={row.id}>
              <legend>Input row {rowNumber}</legend>
              <label>
                Target
                <input
                  aria-label={`Target for row ${rowNumber}`}
                  onChange={(event) => editRow(row.id, (current) => ({ ...current, target: event.target.value }))}
                  type="text"
                  value={row.target}
                />
              </label>
              {field !== null && source !== null ? (
                <SchemaFieldControl
                  diagnostics={[]}
                  field={field}
                  onArrayItemRemove={() => undefined}
                  onSourceChange={(_changedField, nextSource: FieldSource) => editRow(row.id, (current) =>
                    nextSource.mode === "bind"
                      ? { ...current, mode: "path", sourcePath: nextSource.sourcePath }
                      : { ...current, mode: "literal", value: nextSource.value, jsonText: null },
                  )}
                  onValueChange={(_changedField, value) => editRow(row.id, (current) => ({ ...current, value, jsonText: null }))}
                  sourceSuggestions={[]}
                  sources={source}
                  value={row.value}
                />
              ) : (
                <>
                  <fieldset className="schema-form__source">
                    <legend>Value source</legend>
                    <div className="schema-form__source-options">
                      <label>
                        <input
                          checked={row.mode === "literal"}
                          name={`${row.id}-mode`}
                          onChange={() => editRow(row.id, (current) => ({ ...current, mode: "literal" }))}
                          type="radio"
                        />
                        Literal
                      </label>
                      <label>
                        <input
                          checked={row.mode === "path"}
                          name={`${row.id}-mode`}
                          onChange={() => editRow(row.id, (current) => ({ ...current, mode: "path" }))}
                          type="radio"
                        />
                        Bind
                      </label>
                    </div>
                    {row.mode === "path" ? (
                      <label>
                        Source path
                        <input
                          aria-label={`Source path for row ${rowNumber}`}
                          onChange={(event) => editRow(row.id, (current) => ({ ...current, sourcePath: event.target.value }))}
                          type="text"
                          value={row.sourcePath}
                        />
                      </label>
                    ) : (
                      <label>
                        Literal JSON value
                        <textarea
                          aria-label={`Literal JSON value for row ${rowNumber}`}
                          onChange={(event) => editRow(row.id, (current) => ({ ...current, jsonText: event.target.value, value: event.target.value }))}
                          value={row.jsonText ?? jsonText(row.value)}
                        />
                      </label>
                    )}
                  </fieldset>
                  <p className="schema-form__fallback-reason">
                    No matching schema field. Edit the binding as raw JSON.
                  </p>
                </>
              )}
              {issues.length > 0 && (
                <div className="schema-form__diagnostics" role="alert">
                  {issues.map((issue) => <p key={issue}>{issue}</p>)}
                </div>
              )}
              <div className="schema-form__source-options">
                <button
                  aria-label={`Move input row ${rowNumber} up`}
                  className="schema-form__secondary-action"
                  disabled={index === 0}
                  onClick={() => moveRow(index, -1)}
                  type="button"
                >
                  Move up
                </button>
                <button
                  aria-label={`Move input row ${rowNumber} down`}
                  className="schema-form__secondary-action"
                  disabled={index === rows.length - 1}
                  onClick={() => moveRow(index, 1)}
                  type="button"
                >
                  Move down
                </button>
                <button
                  aria-label={`Remove input row ${rowNumber}`}
                  className="schema-form__secondary-action"
                  onClick={() => removeRow(row.id)}
                  type="button"
                >
                  Remove
                </button>
              </div>
            </fieldset>
          );
        })}
        <button className="schema-form__secondary-action" onClick={addRow} type="button">
          Add input row
        </button>
      </div>
      <div className="schema-form__source-options">
        <button type="submit">{submitLabel}</button>
        <button onClick={clear} type="button">Clear inputs</button>
      </div>
    </form>
  );
};
