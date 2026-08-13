import { useState } from "react";
import { SchemaFieldControl } from "../schema-form/SchemaFieldControl.js";
import { rebaseSchemaField, type SchemaField } from "../schema-form/schema-field.js";
import type { FieldSources } from "../schema-form/schema-values.js";
import type { ExpressionEditorState } from "./input-expression-editor.js";

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

const defaultLiteralValue = (field: SchemaField | null): unknown => {
  if (field?.hasDefault) return field.defaultValue;
  if (field?.kind === "boolean") return false;
  if (field?.kind === "number" || field?.kind === "integer") return 0;
  if (field?.kind === "enum") return field.enumValues[0] ?? null;
  return "";
};

export const defaultExpressionEditorState = (
  field: SchemaField | null,
): ExpressionEditorState => {
  if (field?.kind === "array") return { kind: "array", items: [] };
  if (field?.kind === "object") {
    return {
      kind: "object",
      fields: field.children.map((child) => ({
        name: child.key,
        value: defaultExpressionEditorState(child),
      })),
    };
  }
  return { kind: "literal", value: defaultLiteralValue(field), touched: false };
};

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
      : { kind: "literal", value: defaultLiteralValue(field), touched: true };
  }
  return isConstructField(field) ? defaultExpressionEditorState(field) : current;
};

const fieldForName = (field: SchemaField | null, name: string): SchemaField | null => {
  if (field?.kind !== "object") return null;
  return field.children.find((child) => child.key === name) ??
    (field.additionalPropertiesKind === "schema" ? field.additionalProperty : null);
};

const labelForName = (label: string, name: string): string =>
  `${label} field ${name}`;

const pathNeedsDeferredValidation = (field: SchemaField | null, path: string): boolean =>
  path.startsWith("context.") ||
  field === null ||
  field.fallbackReason === "The schema is unconstrained; edit JSON directly.";

const InputExpressionLeaf = ({
  field,
  label,
  onChange,
  sourceSuggestions,
  state,
}: {
  readonly field: SchemaField | null;
  readonly label: string;
  readonly onChange: (state: ExpressionEditorState) => void;
  readonly sourceSuggestions: ReadonlyArray<string>;
  readonly state: ExpressionEditorState;
}) => {
  if (state.kind === "path") {
    return (
      <div className="input-expression-control__leaf">
        <label>
          Path for {label}
          <input
            aria-label={`Path for ${label}`}
            list={`${label.replaceAll(/[^a-zA-Z0-9]+/g, "-")}-paths`}
            onChange={(event) => onChange({ ...state, path: event.target.value, touched: true })}
            type="text"
            value={state.path}
          />
        </label>
        <datalist id={`${label.replaceAll(/[^a-zA-Z0-9]+/g, "-")}-paths`}>
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

  const sources: FieldSources = {};
  return (
    <div className="input-expression-control__leaf">
      <SchemaFieldControl
        diagnostics={[]}
        field={field}
        onArrayItemRemove={() => undefined}
        onSourceChange={() => undefined}
        onValueChange={(_, value) => onChange({ ...literalState, value, touched: true })}
        showSourceControl={false}
        sources={sources}
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
  const [additionalName, setAdditionalName] = useState("");
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
        return (
          <fieldset
            aria-label={itemLabel}
            className="input-expression-control__item"
            key={`${itemLabel}-${index}`}
          >
            <InputExpressionControl
              field={itemField}
              label={itemLabel}
              onChange={(next) => onChange({
                kind: "array",
                items: state.items.map((candidate, candidateIndex) => candidateIndex === index ? next : candidate),
              })}
              sourceSuggestions={sourceSuggestions}
              state={item}
            />
            <div className="input-expression-control__item-actions">
              <button
                aria-label={`Move ${itemLabel} up`}
                className="schema-form__secondary-action"
                disabled={index === 0}
                onClick={() => onChange({
                  kind: "array",
                  items: state.items.map((candidate, candidateIndex) =>
                    candidateIndex === index - 1
                      ? state.items[index]!
                      : candidateIndex === index
                        ? state.items[index - 1]!
                        : candidate,
                  ),
                })}
                type="button"
              >
                Move up
              </button>
              <button
                aria-label={`Move ${itemLabel} down`}
                className="schema-form__secondary-action"
                disabled={index === state.items.length - 1}
                onClick={() => onChange({
                  kind: "array",
                  items: state.items.map((candidate, candidateIndex) =>
                    candidateIndex === index
                      ? state.items[index + 1]!
                      : candidateIndex === index + 1
                        ? state.items[index]!
                        : candidate,
                  ),
                })}
                type="button"
              >
                Move down
              </button>
              <button
                aria-label={`Remove ${itemLabel}`}
                className="schema-form__secondary-action"
                onClick={() => onChange({ kind: "array", items: state.items.filter((_, itemIndex) => itemIndex !== index) })}
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
        onClick={() => onChange({ kind: "array", items: [...state.items, defaultExpressionEditorState(field?.item ?? null)] })}
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
