import { useRef, useState, type FormEvent } from "react";
import { formatBoundedJson } from "../domain/format-bounded-json.js";
import type { JsonObject } from "../domain/draft-workspace-models.js";
import {
  projectWorkflowSchema,
  serializeWorkflowSchema,
  type WorkflowContractKind,
  type WorkflowSchemaFieldRow,
  type WorkflowSchemaFieldType,
} from "./workflow-contract-editor.js";

type WorkflowSchemaFieldsFormProps = {
  readonly contract: Extract<WorkflowContractKind, "input" | "state" | "output">;
  readonly schema: unknown;
  readonly onSubmit: (schema: JsonObject) => void | Promise<void>;
  readonly onDirtyChange?: (dirty: boolean) => void;
};

const FIELD_TYPES: ReadonlyArray<WorkflowSchemaFieldType> = [
  "value",
  "string",
  "integer",
  "number",
  "boolean",
  "object",
  "array",
];

const updateTree = (
  rows: ReadonlyArray<WorkflowSchemaFieldRow>,
  id: string,
  update: (row: WorkflowSchemaFieldRow) => WorkflowSchemaFieldRow,
): ReadonlyArray<WorkflowSchemaFieldRow> => rows.map((row) => {
  if (row.id === id) return update(row);
  const children = updateTree(row.children, id, update);
  const itemRows = row.item === null ? [] : updateTree([row.item], id, update);
  const item = itemRows[0] ?? null;
  return children === row.children && item === row.item ? row : { ...row, children, item };
});

const removeFromTree = (
  rows: ReadonlyArray<WorkflowSchemaFieldRow>,
  id: string,
): ReadonlyArray<WorkflowSchemaFieldRow> => rows
  .filter((row) => row.id !== id)
  .map((row) => ({
    ...row,
    children: removeFromTree(row.children, id),
    item: row.item === null ? null : removeFromTree([row.item], id)[0] ?? null,
  }));

const emptyRow = (id: string, name = "field"): WorkflowSchemaFieldRow => ({
  id,
  name,
  type: "string",
  required: false,
  description: "",
  hasDefault: false,
  defaultValue: undefined,
  reducer: undefined,
  children: [],
  item: null,
  unsupportedReason: null,
  raw: {},
});

const parseJsonValue = (value: string): unknown => {
  if (value.trim() === "") return undefined;
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
};

type FieldEditorProps = {
  readonly row: WorkflowSchemaFieldRow;
  readonly state: boolean;
  readonly onUpdate: (id: string, update: (row: WorkflowSchemaFieldRow) => WorkflowSchemaFieldRow) => void;
  readonly onRemove: (id: string) => void;
  readonly createId: () => string;
};

const FieldEditor = ({ row, state, onUpdate, onRemove, createId }: FieldEditorProps) => {
  if (row.unsupportedReason !== null) {
    return (
      <fieldset aria-label={`Unsupported field ${row.name}`} className="workflow-schema-field workflow-schema-field--unsupported">
        <legend>{row.name}</legend>
        <p>{row.unsupportedReason}</p>
        <details>
          <summary>Advanced field details</summary>
          <pre role="region" tabIndex={0}>{formatBoundedJson(row.raw)}</pre>
        </details>
        <button onClick={() => onRemove(row.id)} type="button">Remove unsupported field</button>
      </fieldset>
    );
  }
  const set = (patch: Partial<WorkflowSchemaFieldRow>): void =>
    onUpdate(row.id, (current) => ({ ...current, ...patch }));
  return (
    <fieldset aria-label={`Schema field ${row.name}`} className="workflow-schema-field">
      <legend>{row.name || "Unnamed field"}</legend>
      <label>
        Field name
        <input onChange={(event) => set({ name: event.target.value })} value={row.name} />
      </label>
      <label>
        Type
        <select
          onChange={(event) => {
            const type = event.target.value as WorkflowSchemaFieldType;
            set({
              type,
              children: type === "object" ? row.children : [],
              item: type === "array" ? row.item ?? emptyRow(`${row.id}.items`, "item") : null,
            });
          }}
          value={row.type}
        >
          {FIELD_TYPES.map((type) => <option key={type} value={type}>{type}</option>)}
        </select>
      </label>
      <label>
        <input
          checked={row.required}
          onChange={(event) => set({ required: event.target.checked })}
          type="checkbox"
        />
        Required
      </label>
      <label>
        Description
        <input onChange={(event) => set({ description: event.target.value })} value={row.description} />
      </label>
      {state && (
        <div className="workflow-schema-field__state">
          <label>
            <input
              checked={row.hasDefault}
              onChange={(event) => set({ hasDefault: event.target.checked })}
              type="checkbox"
            />
            Has default
          </label>
          {row.hasDefault && (
            <label>
              Default JSON
              <textarea
                onChange={(event) => set({ defaultValue: parseJsonValue(event.target.value) })}
                value={JSON.stringify(row.defaultValue) ?? ""}
              />
            </label>
          )}
          <label>
            Reducer
            <input
              onChange={(event) => set({ reducer: parseJsonValue(event.target.value) })}
              placeholder="wf.std.replace"
              value={typeof row.reducer === "string" ? row.reducer : JSON.stringify(row.reducer) ?? ""}
            />
          </label>
        </div>
      )}
      {row.type === "object" && (
        <div className="workflow-schema-field__children">
          <h4>Object fields</h4>
          {row.children.map((child) => (
            <FieldEditor
              createId={createId}
              key={child.id}
              onRemove={onRemove}
              onUpdate={onUpdate}
              row={child}
              state={state}
            />
          ))}
          <button
            onClick={() => onUpdate(row.id, (current) => ({
              ...current,
              children: [...current.children, emptyRow(createId())],
            }))}
            type="button"
          >
            Add nested field
          </button>
        </div>
      )}
      {row.type === "array" && row.item !== null && (
        <div className="workflow-schema-field__children">
          <h4>Array item</h4>
          <FieldEditor
            createId={createId}
            onRemove={() => set({ item: emptyRow(`${row.id}.items`, "item") })}
            onUpdate={onUpdate}
            row={row.item}
            state={state}
          />
        </div>
      )}
      <button onClick={() => onRemove(row.id)} type="button">Remove field</button>
    </fieldset>
  );
};

export const WorkflowSchemaFieldsForm = ({
  contract,
  schema,
  onSubmit,
  onDirtyChange,
}: WorkflowSchemaFieldsFormProps) => {
  const [projection] = useState(() => projectWorkflowSchema(schema));
  const [rows, setRows] = useState(projection.rows);
  const nextId = useRef(0);
  const markDirty = (): void => onDirtyChange?.(true);
  const createId = (): string => `new-field-${nextId.current++}`;
  const update = (
    id: string,
    updater: (row: WorkflowSchemaFieldRow) => WorkflowSchemaFieldRow,
  ): void => {
    setRows((current) => updateTree(current, id, updater));
    markDirty();
  };
  const remove = (id: string): void => {
    setRows((current) => removeFromTree(current, id));
    markDirty();
  };
  const submit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    void Promise.resolve(
      onSubmit(serializeWorkflowSchema(projection, rows, { state: contract === "state" })),
    ).catch(() => undefined);
  };

  return (
    <form className="workflow-schema-fields-form" noValidate onSubmit={submit}>
      {projection.rootUnsupportedReason !== null ? (
        <section aria-label="Unsupported root schema" className="workflow-schema-field--unsupported">
          <p>{projection.rootUnsupportedReason}</p>
          <details>
            <summary>Advanced schema details</summary>
            <pre role="region" tabIndex={0}>{formatBoundedJson(projection.schema)}</pre>
          </details>
        </section>
      ) : (
        <>
          {rows.length === 0 && <p>No fields declared.</p>}
          {rows.map((row) => (
            <FieldEditor
              createId={createId}
              key={row.id}
              onRemove={remove}
              onUpdate={update}
              row={row}
              state={contract === "state"}
            />
          ))}
          <button
            onClick={() => {
              setRows((current) => [...current, emptyRow(createId())]);
              markDirty();
            }}
            type="button"
          >
            Add field
          </button>
          <button type="submit">Save {contract} schema</button>
        </>
      )}
    </form>
  );
};
