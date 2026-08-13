import { useId, useState } from "react";
import { SchemaFieldControl } from "../schema-form/SchemaFieldControl.js";
import { rebaseSchemaField, type SchemaField } from "../schema-form/schema-field.js";
import type { FieldSources } from "../schema-form/schema-values.js";
import {
  defaultExpressionEditorState,
  type ExpressionEditorState,
} from "./input-expression-editor.js";

export type InputExpressionControlProps = {
  readonly field: SchemaField | null;
  readonly label: string;
  readonly onChange: (state: ExpressionEditorState) => void;
  readonly sourceSuggestions?: ReadonlyArray<string>;
  readonly state: ExpressionEditorState;
  readonly showModeControl?: boolean;
};

const isConstructField = (field: SchemaField | null): boolean =>
  field?.kind === "array" || field?.kind === "object";

const valueSourceFor = (state: ExpressionEditorState): "path" | "literal" | "construct" =>
  state.kind === "array" || state.kind === "object" ? "construct" : state.kind;

const stateForSource = (
  source: "path" | "literal" | "construct",
  field: SchemaField | null,
  current: ExpressionEditorState,
): ExpressionEditorState => {
  if (source === "path") {
    return current.kind === "path"
      ? current
      : { kind: "path", path: "input.", touched: true };
  }
  if (source === "literal") {
    return current.kind === "literal"
      ? current
      : (() => {
        const defaultState = defaultExpressionEditorState(field);
        return {
          kind: "literal" as const,
          value: defaultState.kind === "literal" ? defaultState.value : null,
          touched: true,
        };
      })();
  }
  return isConstructField(field) ? defaultExpressionEditorState(field) : current;
};

const fieldForName = (field: SchemaField | null, name: string): SchemaField | null => {
  if (field?.kind !== "object") return null;
  return field.children.find((child) => child.key === name) ??
    (field.additionalPropertiesKind === "schema" ? field.additionalProperty : null);
};

const missingRequiredProperties = (
  field: SchemaField | null,
  fields: ReadonlyArray<{ readonly name: string }>,
): ReadonlyArray<SchemaField> => {
  if (field?.kind !== "object") return [];
  const presentNames = new Set<string>();
  for (const entry of fields) presentNames.add(entry.name);
  const missing: SchemaField[] = [];
  for (const child of field.children) {
    if (child.required && !presentNames.has(child.key)) missing.push(child);
  }
  return missing;
};

const labelForName = (label: string, name: string): string =>
  `${label} field ${name}`;

const pathNeedsDeferredValidation = (field: SchemaField | null, path: string): boolean =>
  path.startsWith("context.") ||
  field === null ||
  field.fallbackReason === "The schema is unconstrained; edit JSON directly.";

const safeIdSuffix = (value: string): string =>
  value.replaceAll(/[^a-zA-Z0-9_-]/g, "-");

const EMPTY_FIELD_SOURCES: FieldSources = {};

const InputExpressionLeaf = ({
  field,
  label,
  onChange,
  sourceSuggestions,
  state,
  idPrefix,
}: {
  readonly field: SchemaField | null;
  readonly idPrefix: string;
  readonly label: string;
  readonly onChange: (state: ExpressionEditorState) => void;
  readonly sourceSuggestions: ReadonlyArray<string>;
  readonly state: ExpressionEditorState;
}) => {
  if (state.kind === "path") {
    const pathListId = `${idPrefix}-paths`;
    return (
      <div className="input-expression-control__leaf">
        <label>
          Path for {label}
          <input
            aria-label={`Path for ${label}`}
            list={pathListId}
            onChange={(event) => onChange({ ...state, path: event.target.value, touched: true })}
            type="text"
            value={state.path}
          />
        </label>
        <datalist id={pathListId}>
          {sourceSuggestions.map((suggestion) => <option key={suggestion} value={suggestion} />)}
        </datalist>
        {pathNeedsDeferredValidation(field, state.path) && (
          <p className="schema-form__fallback-reason">Validated when the workflow runs</p>
        )}
      </div>
    );
  }

  const literalState = state.kind === "literal"
    ? state
    : { kind: "literal" as const, value: null, touched: true };
  if (field === null) {
    const text = typeof literalState.value === "string"
      ? literalState.value
      : JSON.stringify(literalState.value, null, 2) ?? "";
    return (
      <label>
        Literal value for {label}
        <textarea
          aria-label={`Literal value for ${label}`}
          onChange={(event) => {
            try {
              onChange({ ...literalState, value: JSON.parse(event.target.value), touched: true });
            } catch {
              onChange({ ...literalState, value: event.target.value, touched: true });
            }
          }}
          value={text}
        />
      </label>
    );
  }

  return (
    <div className="input-expression-control__leaf">
      <SchemaFieldControl
        diagnostics={[]}
        field={field}
        onArrayItemRemove={() => undefined}
        onSourceChange={() => undefined}
        onValueChange={(_, value) => onChange({ ...literalState, value, touched: true })}
        showSourceControl={false}
        idPrefix={`${idPrefix}-leaf`}
        sources={EMPTY_FIELD_SOURCES}
        value={literalState.value}
      />
    </div>
  );
};

export const InputExpressionControl = ({
  field,
  label,
  onChange,
  sourceSuggestions = [],
  state,
  showModeControl = true,
}: InputExpressionControlProps) => {
  const controlId = `input-expression-${safeIdSuffix(useId())}`;
  const [itemIdentity] = useState(() => ({
    byState: new WeakMap<ExpressionEditorState, string>(),
    nextId: 0,
  }));
  const [additionalName, setAdditionalName] = useState("");
  const identityForItem = (item: ExpressionEditorState): string => {
    const existing = itemIdentity.byState.get(item);
    if (existing !== undefined) return existing;
    const id = `${controlId}-item-${itemIdentity.nextId}`;
    itemIdentity.nextId += 1;
    itemIdentity.byState.set(item, id);
    return id;
  };
  const arrayItemIds = state.kind === "array"
    ? state.items.map(identityForItem)
    : [];
  const rememberItemIdentity = (item: ExpressionEditorState, id: string | undefined): void => {
    if (id !== undefined) itemIdentity.byState.set(item, id);
  };
  const source = valueSourceFor(state);
  const selectSource = (next: "path" | "literal" | "construct"): void =>
    onChange(stateForSource(next, field, state));

  const content = state.kind === "array" ? (
    <fieldset className="input-expression-control__construct" aria-label={label}>
      <legend>{label}</legend>
      {field?.description && <p>{field.description}</p>}
      {state.items.map((item, index) => {
        const itemField = field?.kind === "array" && field.item !== null
          ? rebaseSchemaField(field.item, [...field.path, index])
          : null;
        const itemLabel = `${label} item ${index + 1}`;
        const itemId = arrayItemIds[index]!;
        return (
          <fieldset
            aria-label={itemLabel}
            className="input-expression-control__item"
            key={itemId}
          >
            <InputExpressionControl
              field={itemField}
              label={itemLabel}
              onChange={(next) => {
                rememberItemIdentity(next, itemId);
                onChange({
                  kind: "array",
                  items: state.items.map((candidate, candidateIndex) => candidateIndex === index ? next : candidate),
                });
              }}
              sourceSuggestions={sourceSuggestions}
              state={item}
            />
            <div className="input-expression-control__item-actions">
              <button
                aria-label={`Move ${itemLabel} up`}
                className="schema-form__secondary-action"
                disabled={index === 0}
                onClick={() => {
                  onChange({
                  kind: "array",
                  items: state.items.map((candidate, candidateIndex) =>
                    candidateIndex === index - 1
                      ? state.items[index]!
                      : candidateIndex === index
                        ? state.items[index - 1]!
                        : candidate,
                  ),
                  });
                }}
                type="button"
              >
                Move up
              </button>
              <button
                aria-label={`Move ${itemLabel} down`}
                className="schema-form__secondary-action"
                disabled={index === state.items.length - 1}
                onClick={() => {
                  onChange({
                  kind: "array",
                  items: state.items.map((candidate, candidateIndex) =>
                    candidateIndex === index
                      ? state.items[index + 1]!
                      : candidateIndex === index + 1
                        ? state.items[index]!
                        : candidate,
                  ),
                  });
                }}
                type="button"
              >
                Move down
              </button>
              <button
                aria-label={`Remove ${itemLabel}`}
                className="schema-form__secondary-action"
                onClick={() => {
                  onChange({ kind: "array", items: state.items.filter((_, itemIndex) => itemIndex !== index) });
                }}
                type="button"
              >
                Remove
              </button>
            </div>
          </fieldset>
        );
      })}
      <button
        className="schema-form__secondary-action"
        onClick={() => {
          const item = defaultExpressionEditorState(field?.item ?? null);
          const itemId = `${controlId}-item-${itemIdentity.nextId}`;
          itemIdentity.nextId += 1;
          itemIdentity.byState.set(item, itemId);
          onChange({ kind: "array", items: [...state.items, item] });
        }}
        type="button"
      >
        Add item to {label}
      </button>
    </fieldset>
  ) : state.kind === "object" ? (
    <fieldset className="input-expression-control__construct" aria-label={label}>
      <legend>{label}</legend>
      {field?.description && <p>{field.description}</p>}
      {state.fields.map((entry) => {
        const childField = fieldForName(field, entry.name);
        const declaredField = field?.kind === "object" && field.children.some((child) => child.key === entry.name);
        const childLabel = childField === null && field?.additionalPropertiesKind !== "schema"
          ? labelForName(label, entry.name)
          : `${label}.${entry.name}`;
        return (
          <fieldset
            aria-label={childLabel}
            className="input-expression-control__field"
            key={entry.name}
          >
            <InputExpressionControl
              field={childField}
              label={childLabel}
              onChange={(next) => onChange({
                kind: "object",
                fields: state.fields.map((candidate) => candidate.name === entry.name
                  ? { ...candidate, value: next }
                  : candidate),
              })}
              sourceSuggestions={sourceSuggestions}
              state={entry.value}
            />
            {!declaredField && (
              <div className="input-expression-control__item-actions">
                <button
                  aria-label={`Remove ${childLabel}`}
                  className="schema-form__secondary-action"
                  onClick={() => onChange({
                    kind: "object",
                    fields: state.fields.filter((candidate) => candidate.name !== entry.name),
                  })}
                  type="button"
                >
                  Remove {entry.name}
                </button>
              </div>
            )}
          </fieldset>
        );
      })}
      {missingRequiredProperties(field, state.fields).map((child) => (
          <button
            aria-label={`Add required property ${child.key} to ${label}`}
            className="schema-form__secondary-action"
            key={`required-${child.key}`}
            onClick={() => onChange({
              kind: "object",
              fields: [...state.fields, {
                name: child.key,
                value: defaultExpressionEditorState(child),
              }],
            })}
            type="button"
          >
            Add required property {child.key}
          </button>
        ))}
      {(field?.additionalPropertiesKind === "allowed" || field?.additionalPropertiesKind === "schema") && (
        <div className="input-expression-control__additional">
          <label>
            Additional property name for {label}
            <input
              aria-label={`Additional property name for ${label}`}
              onChange={(event) => setAdditionalName(event.target.value)}
              type="text"
              value={additionalName}
            />
          </label>
          <button
            className="schema-form__secondary-action"
            disabled={additionalName.trim() === "" || state.fields.some((entry) => entry.name === additionalName.trim())}
            onClick={() => {
              const name = additionalName.trim();
              if (name === "" || state.fields.some((entry) => entry.name === name)) return;
              onChange({
                kind: "object",
                fields: [...state.fields, {
                  name,
                  value: defaultExpressionEditorState(field.additionalProperty),
                }],
              });
              setAdditionalName("");
            }}
            type="button"
          >
            Add property to {label}
          </button>
        </div>
      )}
    </fieldset>
  ) : (
    <InputExpressionLeaf
      field={field}
      idPrefix={`${controlId}-leaf`}
      label={label}
      onChange={onChange}
      sourceSuggestions={sourceSuggestions}
      state={state}
    />
  );

  return (
    <div className="input-expression-control">
      {showModeControl && (
        <label className="input-expression-control__mode">
          Value source for {label}
          <select
            aria-label={`Value source for ${label}`}
            onChange={(event) => selectSource(event.target.value as "path" | "literal" | "construct")}
            value={source}
          >
            <option value="path">Path</option>
            <option value="literal">Literal</option>
            {isConstructField(field) && <option value="construct">Construct</option>}
          </select>
        </label>
      )}
      {content}
    </div>
  );
};
