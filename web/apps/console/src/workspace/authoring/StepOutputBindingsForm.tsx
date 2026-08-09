import { useId, useRef, useState, type FormEvent } from "react";
import type {
  DraftDiagnostic,
  LocalInputPath,
  OutputBinding,
  StatePath,
} from "../domain/draft-workspace-models.js";
import { formatBoundedJson } from "./format-bounded-json.js";
import {
  capabilityLocalPathSuggestions,
  inferredStateSchemaPreview,
  outputBindingRows,
  serializeOutputBindingRow,
  stateTargetSuggestions,
  type OutputBindingRow,
} from "./selected-step-dataflow.js";
import { formatTOMLPath } from "../schema-form/schema-paths.js";

type EditableRow = {
  readonly kind: "canonical";
  readonly id: string;
  readonly rawIndex: number;
  readonly sourcePath: string;
  readonly target: string;
};

type UnsupportedRow = Extract<OutputBindingRow, { readonly kind: "unsupported" }> & {
  readonly id: string;
};

type FormRow = EditableRow | UnsupportedRow;

export type StepOutputBindingsFormProps = {
  readonly outputSchema: unknown;
  readonly stateSchema: unknown;
  readonly initialRows?: ReadonlyArray<OutputBindingRow>;
  readonly initialBindings?: ReadonlyArray<OutputBinding>;
  readonly rowDiagnostics?: Readonly<Record<number, ReadonlyArray<DraftDiagnostic>>>;
  readonly onSubmit: (bindings: ReadonlyArray<OutputBinding>) => void | Promise<void>;
  readonly onDirtyChange?: (dirty: boolean) => void;
  readonly submitLabel?: string;
};

const EMPTY_ROWS: ReadonlyArray<OutputBindingRow> = [];
const EMPTY_DIAGNOSTICS: Readonly<Record<number, ReadonlyArray<DraftDiagnostic>>> = {};
const CUSTOM_SOURCE = "__custom__";
const CLEAR_COPY =
  "Saving a new target asks the workflow API to project this output schema into state. Clearing bindings does not delete existing state fields.";

const displayLocalPath = (value: LocalInputPath): string =>
  typeof value === "string" ? value : formatTOMLPath(value.parts);

const displayStatePath = (value: StatePath): string =>
  typeof value === "string" ? value : formatTOMLPath(value.parts);

const rowsFrom = (
  rows: ReadonlyArray<OutputBindingRow>,
  formId: string,
): ReadonlyArray<FormRow> => rows.map((row, index) => {
  if (row.kind === "unsupported") return { ...row, id: `${formId}-output-row-${index}` };
  return {
    kind: "canonical",
    id: `${formId}-output-row-${index}`,
    rawIndex: row.index,
    sourcePath: displayLocalPath(row.value.source),
    target: displayStatePath(row.value.target),
  };
});

const outputRows = (
  initialRows: ReadonlyArray<OutputBindingRow> | undefined,
  initialBindings: ReadonlyArray<OutputBinding> | undefined,
): ReadonlyArray<OutputBindingRow> => {
  if (initialRows !== undefined) return initialRows;
  return initialBindings === undefined ? EMPTY_ROWS : outputBindingRows(initialBindings);
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

const bindingForRow = (
  row: EditableRow,
): { readonly binding: OutputBinding | null; readonly issues: ReadonlyArray<string> } => {
  if (row.sourcePath.trim() === "") return { binding: null, issues: ["Source path is required."] };
  if (row.target.trim() === "") return { binding: null, issues: ["Target is required."] };
  const binding = serializeOutputBindingRow({ source: row.sourcePath, target: row.target });
  return binding === null
    ? { binding: null, issues: ["Source must be a local path and target must start with state."] }
    : { binding, issues: [] };
};

type EditRow = (id: string, update: (row: EditableRow) => EditableRow) => void;
type MoveRow = (index: number, direction: -1 | 1) => void;

type UnsupportedOutputRowProps = {
  readonly row: UnsupportedRow;
  readonly rowNumber: number;
  readonly rowDiagnostics: Readonly<Record<number, ReadonlyArray<DraftDiagnostic>>>;
  readonly localIssues: Readonly<Record<string, ReadonlyArray<string>>>;
  readonly onRemove: (id: string) => void;
};

const UnsupportedOutputRow = ({
  row,
  rowNumber,
  rowDiagnostics,
  localIssues,
  onRemove,
}: UnsupportedOutputRowProps) => {
  const issues = [
    ...(rowDiagnostics[row.index] ?? []).map((diagnostic) => diagnostic.message),
    ...(localIssues[row.id] ?? []),
  ];
  const errorId = `${row.id}-errors`;
  return (
    <fieldset aria-label={`Unsupported output row ${rowNumber}`} className="schema-form__group">
      <legend>Output row {rowNumber}: unsupported</legend>
      <p className="schema-form__fallback-reason">{row.reason}</p>
      <details className="schema-form__raw">
        <summary>Raw unsupported output</summary>
        <pre aria-label={`Raw unsupported output row ${rowNumber}`} role="region" tabIndex={0}>
          {formatBoundedJson(row.raw)}
        </pre>
      </details>
      {issues.length > 0 && (
        <div className="schema-form__diagnostics" id={errorId} role="alert">
          {issues.map((issue) => <p key={issue}>{issue}</p>)}
        </div>
      )}
      <button
        aria-describedby={issues.length > 0 ? errorId : undefined}
        aria-label={`Remove unsupported output row ${rowNumber}`}
        className="schema-form__secondary-action"
        onClick={() => onRemove(row.id)}
        type="button"
      >
        Remove to repair
      </button>
    </fieldset>
  );
};

type OutputRowEditorProps = {
  readonly row: EditableRow;
  readonly rowNumber: number;
  readonly index: number;
  readonly rowCount: number;
  readonly outputSchema: unknown;
  readonly sourceSuggestions: ReadonlyArray<string>;
  readonly sourceSuggestionSet: ReadonlySet<string>;
  readonly targetListId: string;
  readonly rowDiagnostics: Readonly<Record<number, ReadonlyArray<DraftDiagnostic>>>;
  readonly localIssues: Readonly<Record<string, ReadonlyArray<string>>>;
  readonly onEdit: EditRow;
  readonly onMove: MoveRow;
  readonly onRemove: (id: string) => void;
};

const OutputRowEditor = ({
  row,
  rowNumber,
  index,
  rowCount,
  outputSchema,
  sourceSuggestions,
  sourceSuggestionSet,
  targetListId,
  rowDiagnostics,
  localIssues,
  onEdit,
  onMove,
  onRemove,
}: OutputRowEditorProps) => {
  const issues = rowIssueMessages(row, rowDiagnostics, localIssues);
  const errorId = `${row.id}-errors`;
  const sourceChoice = sourceSuggestionSet.has(row.sourcePath) ? row.sourcePath : CUSTOM_SOURCE;
  const preview = inferredStateSchemaPreview(outputSchema, row.sourcePath, row.target);
  const targetId = `${row.id}-target`;
  const sourceChoiceId = `${row.id}-source-choice`;
  const sourcePathId = `${row.id}-source-path`;
  const hasIssues = issues.length > 0;
  return (
    <fieldset aria-label={`Output row ${rowNumber}`} className="schema-form__group">
      <legend>Output row {rowNumber}</legend>
      <div className="schema-form__output-row-fields">
        <div className="schema-form__field">
          <label htmlFor={sourceChoiceId}>Source choice</label>
          <select
            aria-label={`Source choice for output row ${rowNumber}`}
            id={sourceChoiceId}
            onChange={(event) => onEdit(row.id, (current) => ({
              ...current,
              sourcePath: event.target.value === CUSTOM_SOURCE
                ? current.sourcePath
                : event.target.value,
            }))}
            value={sourceChoice}
          >
            {sourceSuggestions.map((suggestion) => (
              <option key={suggestion} value={suggestion}>
                {suggestion === "." ? "Whole output (.)" : suggestion}
              </option>
            ))}
            <option value={CUSTOM_SOURCE}>Custom local path</option>
          </select>
        </div>
        <label htmlFor={sourcePathId}>
          Local source path
          <input
            aria-describedby={hasIssues ? errorId : undefined}
            aria-invalid={hasIssues}
            aria-label={`Local source path for output row ${rowNumber}`}
            id={sourcePathId}
            onChange={(event) => onEdit(row.id, (current) => ({
              ...current,
              sourcePath: event.target.value,
            }))}
            type="text"
            value={row.sourcePath}
          />
        </label>
        <label htmlFor={targetId}>
          Target
          <input
            aria-describedby={hasIssues ? errorId : undefined}
            aria-invalid={hasIssues}
            aria-label={`Target for output row ${rowNumber}`}
            id={targetId}
            list={targetListId}
            onChange={(event) => onEdit(row.id, (current) => ({
              ...current,
              target: event.target.value,
            }))}
            type="text"
            value={row.target}
          />
        </label>
      </div>
      {preview !== null ? (
        <details className="schema-form__preview">
          <summary>Inferred source schema</summary>
          <pre aria-label={`Inferred schema for output row ${rowNumber}`} role="region" tabIndex={0}>
            {formatBoundedJson(preview)}
          </pre>
        </details>
      ) : <p>No inferred schema for this source path.</p>}
      {hasIssues && (
        <div className="schema-form__diagnostics" id={errorId} role="alert">
          {issues.map((issue) => <p key={issue}>{issue}</p>)}
        </div>
      )}
      <div className="schema-form__source-options">
        <button
          aria-label={`Move output row ${rowNumber} up`}
          className="schema-form__secondary-action"
          disabled={index === 0}
          onClick={() => onMove(index, -1)}
          type="button"
        >
          Move up
        </button>
        <button
          aria-label={`Move output row ${rowNumber} down`}
          className="schema-form__secondary-action"
          disabled={index === rowCount - 1}
          onClick={() => onMove(index, 1)}
          type="button"
        >
          Move down
        </button>
        <button
          aria-label={`Remove output row ${rowNumber}`}
          className="schema-form__secondary-action"
          onClick={() => onRemove(row.id)}
          type="button"
        >
          Remove
        </button>
      </div>
    </fieldset>
  );
};

export const StepOutputBindingsForm = ({
  outputSchema,
  stateSchema,
  initialRows,
  initialBindings,
  rowDiagnostics = EMPTY_DIAGNOSTICS,
  onSubmit,
  onDirtyChange,
  submitLabel = "Save outputs",
}: StepOutputBindingsFormProps) => {
  const formId = useId();
  const sourceSuggestions = capabilityLocalPathSuggestions(outputSchema);
  const sourceSuggestionSet = new Set(sourceSuggestions);
  const targetSuggestions = stateTargetSuggestions(stateSchema);
  const targetListId = `${formId}-state-targets`;
  const formErrorId = `${formId}-form-error`;
  const [rows, setRows] = useState<ReadonlyArray<FormRow>>(() =>
    rowsFrom(outputRows(initialRows, initialBindings), formId),
  );
  const [localIssues, setLocalIssues] = useState<Readonly<Record<string, ReadonlyArray<string>>>>({});
  const [formIssue, setFormIssue] = useState<string | null>(null);
  const [clearConfirmation, setClearConfirmation] = useState(false);
  const nextId = useRef(rows.length);

  const markDirty = (): void => onDirtyChange?.(true);

  const editRow = (id: string, update: (row: EditableRow) => EditableRow): void => {
    setRows((current) => updateRow(current, id, update));
    setFormIssue(null);
    setClearConfirmation(false);
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
    setClearConfirmation(false);
    markDirty();
  };

  const addRow = (): void => {
    const id = `${formId}-output-row-${nextId.current++}`;
    setRows((current) => [
      ...current,
      { kind: "canonical", id, rawIndex: -1, sourcePath: ".", target: "" },
    ]);
    setFormIssue(null);
    markDirty();
  };

  const unsupportedRows = rows.filter((row): row is UnsupportedRow => row.kind === "unsupported");

  const submit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    const nextIssues: Record<string, ReadonlyArray<string>> = {};
    const bindings: OutputBinding[] = [];
    for (const row of rows) {
      if (row.kind === "unsupported") {
        nextIssues[row.id] = ["Remove or repair this unsupported output row before saving."];
        continue;
      }
      const result = bindingForRow(row);
      if (result.binding === null) nextIssues[row.id] = result.issues;
      else bindings.push(result.binding);
    }
    setLocalIssues(nextIssues);
    setFormIssue(unsupportedRows.length > 0
      ? "Remove or repair every unsupported output row before saving."
      : null);
    if (Object.keys(nextIssues).length > 0) return;
    void Promise.resolve(onSubmit(bindings)).catch(() => undefined);
  };

  const requestClear = (): void => {
    if (unsupportedRows.length > 0) {
      setFormIssue("Remove or repair this unsupported output row before clearing outputs.");
      setClearConfirmation(false);
      markDirty();
      return;
    }
    setFormIssue(CLEAR_COPY);
    setClearConfirmation(true);
    markDirty();
  };

  const confirmClear = (): void => {
    setRows([]);
    setLocalIssues({});
    setFormIssue(null);
    setClearConfirmation(false);
    markDirty();
    void Promise.resolve(onSubmit([])).catch(() => undefined);
  };

  return (
    <form className="schema-form authoring-form output-bindings-form" noValidate onSubmit={submit}>
      {formIssue !== null && <p id={formErrorId} role="alert">{formIssue}</p>}
      <datalist id={targetListId}>
        {targetSuggestions.map((suggestion) => <option key={suggestion} value={suggestion} />)}
      </datalist>
      <p className="schema-form__note">{CLEAR_COPY}</p>
      <div className="schema-form__group">
        {rows.length === 0 && <p>No output bindings configured.</p>}
        {rows.map((row, index) => row.kind === "unsupported" ? (
          <UnsupportedOutputRow
            key={row.id}
            localIssues={localIssues}
            onRemove={removeRow}
            row={row}
            rowDiagnostics={rowDiagnostics}
            rowNumber={index + 1}
          />
        ) : (
          <OutputRowEditor
            key={row.id}
            index={index}
            localIssues={localIssues}
            onEdit={editRow}
            onMove={moveRow}
            onRemove={removeRow}
            outputSchema={outputSchema}
            row={row}
            rowCount={rows.length}
            rowDiagnostics={rowDiagnostics}
            rowNumber={index + 1}
            sourceSuggestionSet={sourceSuggestionSet}
            sourceSuggestions={sourceSuggestions}
            targetListId={targetListId}
          />
        ))}
        <button className="schema-form__secondary-action" onClick={addRow} type="button">
          Add output row
        </button>
      </div>
      <div className="schema-form__source-options">
        <button type="submit">{submitLabel}</button>
        <button
          aria-describedby={formIssue !== null ? formErrorId : undefined}
          onClick={requestClear}
          type="button"
        >
          Clear outputs
        </button>
      </div>
      {clearConfirmation && (
        <div aria-describedby={formErrorId} className="schema-form__confirmation" role="group">
          <p>Confirm replacing the ordered output bindings with an empty list.</p>
          <div className="schema-form__source-options">
            <button onClick={confirmClear} type="button">Confirm clear outputs</button>
            <button
              className="schema-form__secondary-action"
              onClick={() => { setClearConfirmation(false); setFormIssue(null); }}
              type="button"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </form>
  );
};
