import { useId, useRef, useState, type FormEvent } from "react";
import type {
  DraftDiagnostic,
  StepInputBinding,
} from "../domain/draft-workspace-models.js";
import { InputExpressionControl, defaultExpressionEditorState } from "./InputExpressionControl.js";
import {
  projectExpressionEditorState,
  serializeExpressionEditorState,
  validateExpressionEditorState,
  type ExpressionEditorState,
} from "./input-expression-editor.js";
import { SchemaFieldControl } from "../schema-form/SchemaFieldControl.js";
import { formatTOMLPath, parseGraphSourcePath, parseTOMLPath } from "../schema-form/schema-paths.js";
import {
  normalizeSchema,
  schemaFieldAtPath,
  type SchemaField,
} from "../schema-form/schema-field.js";
import { serializeSchemaValues, type FieldSources } from "../schema-form/schema-values.js";
import { formatBoundedJson } from "../domain/format-bounded-json.js";
import { displayGraphInputPath, displayLocalInputPath } from "./input-binding-paths.js";
import {
  capabilityLocalPathSuggestions,
  isJsonValue,
  serializeInputBindingRow,
  serializeStepInputBindingRow,
  stepInputBindingRows,
  workflowSourceSuggestions,
  type StepInputBindingRow,
} from "./selected-step-dataflow.js";

type EditableRow = {
  readonly kind: "canonical";
  readonly id: string;
  readonly rawIndex: number;
  readonly target: string;
  readonly mode: "path" | "literal" | "expression";
  readonly sourcePath: string;
  readonly value: unknown;
  readonly jsonText: string | null;
  readonly expression: ExpressionEditorState | null;
};

type UnsupportedRow = Extract<StepInputBindingRow, { readonly kind: "unsupported" }> & {
  readonly id: string;
};

type FormRow = EditableRow | UnsupportedRow;

export type StepInputBindingsFormProps = {
  readonly inputSchema: unknown;
  readonly workflowInputSchema?: unknown;
  readonly workflowStateSchema?: unknown;
  readonly initialRows?: ReadonlyArray<StepInputBindingRow>;
  readonly initialBindings?: ReadonlyArray<StepInputBinding>;
  readonly rowDiagnostics?: Readonly<Record<number, ReadonlyArray<DraftDiagnostic>>>;
  readonly onSubmit: (bindings: ReadonlyArray<StepInputBinding>) => void | Promise<void>;
  readonly onDirtyChange?: (dirty: boolean) => void;
  readonly submitLabel?: string;
};

const EMPTY_ROWS: ReadonlyArray<StepInputBindingRow> = [];
const EMPTY_DIAGNOSTICS: Readonly<Record<number, ReadonlyArray<DraftDiagnostic>>> = {};

const jsonText = (value: unknown): string => {
  const encoded = JSON.stringify(value, null, 2);
  return encoded ?? "";
};

const rowsFrom = (
  rows: ReadonlyArray<StepInputBindingRow>,
  formId: string,
  root: SchemaField,
): ReadonlyArray<FormRow> => rows.map((row, index) => {
  if (row.kind === "unsupported") return { ...row, id: `${formId}-input-row-${index}` };
  if ("expression" in row.value) {
    const target = displayLocalInputPath(row.value.target);
    const projection = projectExpressionEditorState(
      row.value.expression,
      schemaFieldForTarget(root, target) ?? {},
    );
    if (projection.kind === "unsupported") {
      return {
        kind: "unsupported",
        field: "input",
        index: row.index,
        raw: row.value,
        reason: projection.reason,
        id: `${formId}-input-row-${index}`,
      };
    }
    return {
      kind: "canonical",
      id: `${formId}-input-row-${index}`,
      rawIndex: row.index,
      target,
      mode: "expression",
      sourcePath: "input.",
      value: null,
      jsonText: null,
      expression: projection.state,
    };
  }
  if ("path" in row.value) {
    return {
      kind: "canonical",
      id: `${formId}-input-row-${index}`,
      rawIndex: row.index,
      target: displayLocalInputPath(row.value.target),
      mode: "path",
      sourcePath: displayGraphInputPath(row.value.path),
      value: null,
      jsonText: null,
      expression: null,
    };
  }
  return {
    kind: "canonical",
    id: `${formId}-input-row-${index}`,
    rawIndex: row.index,
    target: displayLocalInputPath(row.value.target),
    mode: "literal",
    sourcePath: "input.",
    value: row.value.value,
    jsonText: null,
    expression: null,
  };
});

const inputRows = (
  initialRows: ReadonlyArray<StepInputBindingRow> | undefined,
  initialBindings: ReadonlyArray<StepInputBinding> | undefined,
): ReadonlyArray<StepInputBindingRow> => {
  if (initialRows !== undefined) return initialRows;
  return initialBindings === undefined ? EMPTY_ROWS : stepInputBindingRows(initialBindings);
};

const updateRow = (
  rows: ReadonlyArray<FormRow>,
  id: string,
  update: (row: EditableRow) => EditableRow,
): ReadonlyArray<FormRow> => rows.map((row) =>
  row.kind === "canonical" && row.id === id ? update(row) : row,
);

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const setAtPath = (
  current: unknown,
  path: ReadonlyArray<string | number>,
  value: unknown,
): unknown => {
  if (path.length === 0) return value;
  const head = path[0];
  if (head === undefined) return current;
  const tail = path.slice(1);
  if (typeof head === "number") {
    const next = Array.isArray(current) ? [...current] : [];
    next[head] = setAtPath(next[head], tail, value);
    return next;
  }
  const next = isRecord(current) ? { ...current } : {};
  next[head] = setAtPath(next[head], tail, value);
  return next;
};

const removeAtPath = (
  current: unknown,
  path: ReadonlyArray<string | number>,
): unknown => {
  if (path.length === 0) return current;
  const head = path[0];
  if (head === undefined) return current;
  const tail = path.slice(1);
  if (typeof head === "number") {
    if (!Array.isArray(current)) return current;
    if (tail.length === 0) return current.filter((_, index) => index !== head);
    const next = [...current];
    next[head] = removeAtPath(next[head], tail);
    return next;
  }
  if (!isRecord(current)) return current;
  return { ...current, [head]: removeAtPath(current[head], tail) };
};

const relativePath = (
  rootPath: ReadonlyArray<string | number>,
  changedPath: ReadonlyArray<string | number>,
): ReadonlyArray<string | number> => changedPath.slice(rootPath.length);

const rowIssueMessages = (
  row: EditableRow,
  rowDiagnostics: Readonly<Record<number, ReadonlyArray<DraftDiagnostic>>>,
  localIssues: Readonly<Record<string, ReadonlyArray<string>>>,
): ReadonlyArray<string> => [
  ...(rowDiagnostics[row.rawIndex] ?? []).map((diagnostic) => diagnostic.message),
  ...(localIssues[row.id] ?? []),
];

const schemaFieldForTarget = (root: SchemaField, target: string): SchemaField | null => {
  const targetParts = parseTOMLPath(target);
  return targetParts === null
    ? null
    : schemaFieldAtPath(root, targetParts.map((part) => /^\d+$/.test(part) ? Number(part) : part));
};

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
): { readonly binding: StepInputBinding | null; readonly issues: ReadonlyArray<string> } => {
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
  if (row.mode === "expression") {
    if (row.expression === null) return { binding: null, issues: ["Construct an expression before saving."] };
    const field = schemaFieldForTarget(root, target);
    const validation = validateExpressionEditorState(row.expression, field ?? {});
    const expression = serializeExpressionEditorState(row.expression);
    const issues = validation.issues.map((item) => item.message);
    if (expression === null) issues.push("Expression must be valid finite JSON.");
    if (issues.length > 0 || expression === null) return { binding: null, issues };
    const binding = serializeStepInputBindingRow({ target, expression });
    return binding === null
      ? { binding: null, issues: ["Enter a valid expression target."] }
      : { binding, issues: [] };
  }
  const field = schemaFieldForTarget(root, target);
  const literal = literalValueFor(field, row);
  if (literal.issues.length > 0) return { binding: null, issues: literal.issues };
  const binding = serializeInputBindingRow({ target, value: literal.value });
  return binding === null
    ? { binding: null, issues: ["Enter a valid target and JSON literal."] }
    : { binding, issues: [] };
};

export const StepInputBindingsForm = ({
  inputSchema,
  workflowInputSchema,
  workflowStateSchema,
  initialRows,
  initialBindings,
  rowDiagnostics = EMPTY_DIAGNOSTICS,
  onSubmit,
  onDirtyChange,
  submitLabel = "Save inputs",
}: StepInputBindingsFormProps) => {
  const formId = useId();
  const root = normalizeSchema(inputSchema);
  const sourceSuggestions = workflowSourceSuggestions(workflowInputSchema ?? null, workflowStateSchema ?? null);
  const targetSuggestions = capabilityLocalPathSuggestions(inputSchema);
  const sourceListId = `${formId}-workflow-sources`;
  const targetListId = `${formId}-capability-targets`;
  const [rows, setRows] = useState<ReadonlyArray<FormRow>>(() =>
    rowsFrom(inputRows(initialRows, initialBindings), formId, root),
  );
  const [localIssues, setLocalIssues] = useState<Readonly<Record<string, ReadonlyArray<string>>>>({});
  const [formIssue, setFormIssue] = useState<string | null>(null);
  const nextId = useRef(rows.length);
  const formErrorId = `${formId}-form-error`;

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
    setLocalIssues((current) => {
      const next = { ...current };
      delete next[id];
      return next;
    });
    setFormIssue(null);
    markDirty();
  };

  const addRow = (): void => {
    const id = `${formId}-input-row-${nextId.current++}`;
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
        expression: null,
      },
    ]);
    markDirty();
  };

  const unsupportedRows = rows.filter((row): row is UnsupportedRow => row.kind === "unsupported");
  const hasBlockingIssues = rows.some((row) => {
    if (row.kind === "unsupported") return true;
    return rowIssueMessages(row, rowDiagnostics, localIssues).length > 0 ||
      bindingForRow(root, row).issues.length > 0;
  });

  const submit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    const nextIssues: Record<string, ReadonlyArray<string>> = {};
    const completed: Array<{ readonly id: string; readonly binding: StepInputBinding }> = [];
    for (const row of rows) {
      if (row.kind === "unsupported") {
        nextIssues[row.id] = ["Remove or repair this unsupported input row before saving."];
        continue;
      }
      const result = bindingForRow(root, row);
      if (result.binding === null) nextIssues[row.id] = result.issues;
      else completed.push({ id: row.id, binding: result.binding });
    }
    const duplicateRows = new Map<string, string[]>();
    for (const item of completed) {
      const target = displayLocalInputPath(item.binding.target);
      duplicateRows.set(target, [...(duplicateRows.get(target) ?? []), item.id]);
    }
    for (const ids of duplicateRows.values()) {
      if (ids.length < 2) continue;
      for (const id of ids) {
        nextIssues[id] = [
          ...(nextIssues[id] ?? []),
          "Target is duplicated in another input row.",
        ];
      }
    }
    setLocalIssues(nextIssues);
    setFormIssue(unsupportedRows.length > 0
      ? "Remove or repair every unsupported input row before saving."
      : null);
    if (Object.keys(nextIssues).length > 0) return;
    void Promise.resolve(onSubmit(completed.map(({ binding }) => binding))).catch(() => undefined);
  };

  const clear = (): void => {
    if (unsupportedRows.length > 0) {
      const message =
        "Remove or repair this unsupported input row before clearing inputs.";
      setFormIssue(message);
      markDirty();
      return;
    }
    setLocalIssues({});
    setFormIssue(null);
    markDirty();
    void Promise.resolve(onSubmit([]))
      .then(() => setRows([]))
      .catch(() => undefined);
  };
  return (
    <form className="schema-form authoring-form" noValidate onSubmit={submit}>
      {formIssue !== null && <p id={formErrorId} role="alert">{formIssue}</p>}
      <datalist id={sourceListId}>
        {sourceSuggestions.map((suggestion) => <option key={suggestion} value={suggestion} />)}
      </datalist>
      <datalist id={targetListId}>
        {targetSuggestions.map((suggestion) => <option key={suggestion} value={suggestion} />)}
      </datalist>
      <div className="schema-form__group">
        {rows.length === 0 && <p>No input bindings configured.</p>}
        {rows.map((row, index) => {
          const rowNumber = index + 1;
          if (row.kind === "unsupported") {
            const unsupportedIssues = [
              ...(rowDiagnostics[row.index] ?? []).map((diagnostic) => diagnostic.message),
              ...(localIssues[row.id] ?? []),
            ];
            const errorId = `${row.id}-errors`;
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
                  <div className="schema-form__diagnostics" id={errorId} role="alert">
                    {unsupportedIssues.map((issue) => <p key={issue}>{issue}</p>)}
                  </div>
                )}
                <button
                  aria-describedby={unsupportedIssues.length > 0 ? errorId : undefined}
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
          const field = schemaFieldForTarget(root, row.target.trim());
          const issues = [...new Set([
            ...rowIssueMessages(row, rowDiagnostics, localIssues),
            ...bindingForRow(root, row).issues,
          ])];
          const targetId = `${row.id}-target`;
          const errorId = `${row.id}-errors`;
          const pathId = `${row.id}-source-path`;
          const literalId = `${row.id}-literal`;
          const pathModeId = `${row.id}-path-mode`;
          const literalModeId = `${row.id}-literal-mode`;
          const expressionModeId = `${row.id}-expression-mode`;
          const canConstruct = field?.kind === "array" || field?.kind === "object";
          const hasIssues = issues.length > 0;
          const literalSources: FieldSources = field === null
            ? {}
            : { [formatTOMLPath(field.path)]: { mode: "literal", value: row.value } };
          return (
            <fieldset aria-label={`Input row ${rowNumber}`} className="schema-form__group" key={row.id}>
              <legend>Input row {rowNumber}</legend>
              <label htmlFor={targetId}>Target</label>
              <input
                aria-describedby={hasIssues ? errorId : undefined}
                aria-invalid={hasIssues}
                aria-label={`Target for row ${rowNumber}`}
                id={targetId}
                list={targetListId}
                onChange={(event) => editRow(row.id, (current) => ({ ...current, target: event.target.value }))}
                type="text"
                value={row.target}
              />
              <fieldset aria-label={`Source mode for input row ${rowNumber}`} className="schema-form__source">
                <legend>Value source</legend>
                <div className="schema-form__source-options">
                  <label htmlFor={pathModeId}>
                    <input
                      aria-label={`Path for input row ${rowNumber}`}
                      checked={row.mode === "path"}
                      id={pathModeId}
                      name={`${row.id}-mode`}
                      onChange={() => editRow(row.id, (current) => ({ ...current, mode: "path" }))}
                      type="radio"
                    />
                    Path
                  </label>
                  <label htmlFor={literalModeId}>
                    <input
                      aria-label={`Literal value for input row ${rowNumber}`}
                      checked={row.mode === "literal"}
                      id={literalModeId}
                      name={`${row.id}-mode`}
                      onChange={() => editRow(row.id, (current) => ({ ...current, mode: "literal" }))}
                      type="radio"
                    />
                    Literal value
                  </label>
                  {canConstruct && (
                    <label htmlFor={expressionModeId}>
                      <input
                        aria-label={`Construct value for input row ${rowNumber}`}
                        checked={row.mode === "expression"}
                        id={expressionModeId}
                        name={`${row.id}-mode`}
                        onChange={() => editRow(row.id, (current) => ({
                          ...current,
                          mode: "expression",
                          expression: current.expression ?? defaultExpressionEditorState(field),
                        }))}
                        type="radio"
                      />
                      Construct
                    </label>
                  )}
                </div>
              </fieldset>
              {row.mode === "path" ? (
                <label htmlFor={pathId}>
                  Source path for input row {rowNumber}
                  <input
                    aria-describedby={hasIssues ? errorId : undefined}
                    aria-invalid={hasIssues}
                    aria-label={`Source path for input row ${rowNumber}`}
                    id={pathId}
                    list={sourceListId}
                    onChange={(event) => editRow(row.id, (current) => ({ ...current, sourcePath: event.target.value }))}
                    type="text"
                    value={row.sourcePath}
                  />
                </label>
              ) : row.mode === "expression" ? (
                <InputExpressionControl
                  field={field}
                  label={row.target.trim() || `input row ${rowNumber}`}
                  onChange={(next) => editRow(row.id, (current) => ({
                    ...current,
                    expression: next,
                  }))}
                  sourceSuggestions={sourceSuggestions}
                  state={row.expression ?? defaultExpressionEditorState(field)}
                  showModeControl={false}
                />
              ) : field !== null ? (
                <SchemaFieldControl
                  diagnostics={[]}
                  field={field}
                  idPrefix={`${row.id}-schema`}
                  onArrayItemRemove={(arrayField, itemIndex) => editRow(row.id, (current) => ({
                    ...current,
                    value: removeAtPath(current.value, [...relativePath(field.path, arrayField.path), itemIndex]),
                  }))}
                  onSourceChange={() => undefined}
                  onValueChange={(changedField, value) => editRow(row.id, (current) => ({
                    ...current,
                    value: setAtPath(current.value, relativePath(field.path, changedField.path), value),
                  }))}
                  showSourceControl={false}
                  sources={literalSources}
                  value={row.value}
                />
              ) : (
                <label htmlFor={literalId}>
                  Literal JSON value for input row {rowNumber}
                  <textarea
                    aria-describedby={hasIssues ? errorId : undefined}
                    aria-invalid={hasIssues}
                    aria-label={`Literal JSON value for input row ${rowNumber}`}
                    id={literalId}
                    onChange={(event) => editRow(row.id, (current) => ({
                      ...current,
                      jsonText: event.target.value,
                      value: event.target.value,
                    }))}
                    value={row.jsonText ?? jsonText(row.value)}
                  />
                </label>
              )}
              {hasIssues && (
                <div className="schema-form__diagnostics" id={errorId} role="alert">
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
        <button disabled={hasBlockingIssues} type="submit">{submitLabel}</button>
        <button
          aria-describedby={formIssue !== null ? formErrorId : undefined}
          onClick={clear}
          type="button"
        >
          Clear inputs
        </button>
      </div>
    </form>
  );
};
