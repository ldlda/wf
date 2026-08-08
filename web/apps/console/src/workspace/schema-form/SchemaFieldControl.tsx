import type { FieldSource, SchemaField } from "./schema-field.js";
import type { FieldSources, SchemaValueIssue } from "./schema-values.js";
import { BindingSourceControl } from "./BindingSourceControl.js";

const EMPTY_SUGGESTIONS: ReadonlyArray<string> = [];

export type SchemaFieldControlProps = {
  readonly field: SchemaField;
  readonly value: unknown;
  readonly sources: FieldSources;
  readonly diagnostics: ReadonlyArray<SchemaValueIssue>;
  readonly onValueChange: (field: SchemaField, value: unknown) => void;
  readonly onSourceChange: (field: SchemaField, source: FieldSource) => void;
  readonly sourceSuggestions?: ReadonlyArray<string>;
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const pathKey = (field: SchemaField): string =>
  field.path.length === 0 ? "root" : field.path.map(String).join(".");

const samePath = (
  left: ReadonlyArray<string | number>,
  right: ReadonlyArray<string | number>,
): boolean => left.length === right.length && left.every((part, index) => part === right[index]);

const fieldId = (field: SchemaField): string =>
  `schema-field-${pathKey(field).replace(/[^A-Za-z0-9_-]/g, "-")}`;

const displayTitle = (title: string): string =>
  title.length === 0 ? "Value" : `${title.slice(0, 1).toUpperCase()}${title.slice(1)}`;

const jsonText = (value: unknown): string => {
  if (typeof value === "string") return value;
  const encoded = JSON.stringify(value, null, 2);
  return encoded ?? "";
};

const enumValue = (value: string): string => value;

const enumLabel = (value: string | number | boolean | null): string =>
  value === null ? "null" : String(value);

const arrayItemTitle = (field: SchemaField, index: number): string => {
  const base = displayTitle(field.title);
  const singular = base.endsWith("s") ? base.slice(0, -1) : `${base} item`;
  return `${singular} ${index + 1}`;
};

const defaultArrayItemValue = (field: SchemaField): unknown => {
  if (field.hasDefault) return field.defaultValue;
  if (field.kind === "object") return {};
  if (field.kind === "array") return [];
  if (field.kind === "boolean") return false;
  return "";
};

const FieldDiagnostics = ({
  field,
  diagnostics,
}: {
  readonly field: SchemaField;
  readonly diagnostics: ReadonlyArray<SchemaValueIssue>;
}) => {
  if (diagnostics.length === 0) return null;
  return (
    <div className="schema-form__diagnostics" id={`${fieldId(field)}-diagnostics`} role="alert">
      {diagnostics.map((diagnostic) => (
        <p key={`${diagnostic.path.join(".")}-${diagnostic.message}`}>{diagnostic.message}</p>
      ))}
    </div>
  );
};

const FieldLabel = ({ field, id }: { readonly field: SchemaField; readonly id: string }) => (
  <label htmlFor={id}>
    {displayTitle(field.title)}
    {field.required && (
      <>
        <span aria-hidden="true"> *</span>
        <span className="visually-hidden"> required</span>
      </>
    )}
  </label>
);

const LeafControl = ({
  field,
  value,
  onValueChange,
  describedBy,
  invalid,
}: {
  readonly field: SchemaField;
  readonly value: unknown;
  readonly onValueChange: (value: unknown) => void;
  readonly describedBy: string | undefined;
  readonly invalid: boolean;
}) => {
  const id = fieldId(field);
  const label = displayTitle(field.title);
  const common = {
    "aria-describedby": describedBy,
    "aria-invalid": invalid,
    "aria-required": field.required,
    id,
  };
  if (field.kind === "boolean") {
    return (
      <input
        {...common}
        aria-label={label}
        checked={value === true}
        onChange={(event) => onValueChange(event.target.checked)}
        type="checkbox"
      />
    );
  }
  if (field.kind === "enum") {
    return (
      <select
        {...common}
        aria-label={label}
        onChange={(event) => onValueChange(enumValue(event.target.value))}
        value={typeof value === "string" ? value : value === null ? "null" : value === undefined ? "" : String(value)}
      >
        <option value="">Choose {label.toLowerCase()}</option>
        {field.enumValues.map((option) => (
          <option key={JSON.stringify(option)} value={enumLabel(option)}>
            {enumLabel(option)}
          </option>
        ))}
      </select>
    );
  }
  if (field.kind === "number" || field.kind === "integer") {
    return (
      <input
        {...common}
        aria-label={label}
        onChange={(event) => onValueChange(event.target.value)}
        step={field.kind === "integer" ? 1 : "any"}
        type="number"
        value={typeof value === "number" ? String(value) : typeof value === "string" ? value : ""}
      />
    );
  }
  return (
    <textarea
      {...common}
      aria-label={label}
      onChange={(event) => onValueChange(event.target.value)}
      value={field.kind === "string" ? (typeof value === "string" ? value : "") : jsonText(value)}
    />
  );
};

export const SchemaFieldControl = ({
  field,
  value,
  sources,
  diagnostics,
  onValueChange,
  onSourceChange,
  sourceSuggestions = EMPTY_SUGGESTIONS,
}: SchemaFieldControlProps) => {
  const id = fieldId(field);
  const descriptionId = field.description ? `${id}-description` : undefined;
  const fieldDiagnostics = diagnostics.length > 0 ? `${id}-diagnostics` : undefined;
  const describedBy = [descriptionId, fieldDiagnostics].filter(Boolean).join(" ") || undefined;

  if (field.kind === "object") {
    const objectValue = isRecord(value) ? value : {};
    return (
      <fieldset className="schema-form__group" aria-describedby={describedBy}>
        <legend>
          {displayTitle(field.title)}
          {field.required && <span aria-hidden="true"> *</span>}
        </legend>
        {field.description && <p id={descriptionId}>{field.description}</p>}
        {field.children.map((child) => (
          <SchemaFieldControl
            diagnostics={diagnostics.filter((diagnostic) => diagnostic.path.join(".").startsWith(`${child.path.join(".")}`))}
            field={child}
            key={pathKey(child)}
            onSourceChange={onSourceChange}
            onValueChange={onValueChange}
            sourceSuggestions={sourceSuggestions}
            sources={sources}
            value={objectValue[child.key]}
          />
        ))}
        <FieldDiagnostics
          diagnostics={diagnostics.filter((diagnostic) => samePath(diagnostic.path, field.path))}
          field={field}
        />
      </fieldset>
    );
  }

  if (field.kind === "array") {
    const arrayValue = Array.isArray(value) ? value : [];
    return (
      <fieldset className="schema-form__group schema-form__array" aria-describedby={describedBy}>
        <legend>
          {displayTitle(field.title)}
          {field.required && <span aria-hidden="true"> *</span>}
        </legend>
        {field.description && <p id={descriptionId}>{field.description}</p>}
        {arrayValue.map((itemValue, index) => {
          const itemField = field.item ? { ...field.item, path: [...field.path, index], title: arrayItemTitle(field, index) } : null;
          if (!itemField) return null;
          return (
            <div className="schema-form__array-item" key={pathKey(itemField)}>
              <SchemaFieldControl
                diagnostics={diagnostics.filter((diagnostic) => diagnostic.path.join(".") === itemField.path.join("."))}
                field={itemField}
                onSourceChange={onSourceChange}
                onValueChange={onValueChange}
                sourceSuggestions={sourceSuggestions}
                sources={sources}
                value={itemValue}
              />
              <button
                aria-label={`Remove ${arrayItemTitle(field, index).toLowerCase()}`}
                className="schema-form__secondary-action"
                onClick={() => onValueChange(field, arrayValue.filter((_, itemIndex) => itemIndex !== index))}
                type="button"
              >
                Remove
              </button>
            </div>
          );
        })}
        <button
          className="schema-form__secondary-action"
          onClick={() => onValueChange(field, [...arrayValue, defaultArrayItemValue(field.item ?? field)])}
          type="button"
        >
          Add {displayTitle(field.title).replace(/s$/, "").toLowerCase()}
        </button>
        <FieldDiagnostics
          diagnostics={diagnostics.filter((diagnostic) => samePath(diagnostic.path, field.path))}
          field={field}
        />
      </fieldset>
    );
  }

  const source = sources[pathKey(field)] ?? { mode: "literal", value };
  return (
    <div className="schema-form__field">
      <FieldLabel field={field} id={id} />
      {field.description && <p id={descriptionId}>{field.description}</p>}
      <BindingSourceControl
        field={field}
        onChange={(nextSource) => onSourceChange(field, nextSource)}
        source={source}
        suggestions={sourceSuggestions}
      />
      {source.mode === "literal" && (
        <LeafControl
          describedBy={describedBy}
          field={field}
          invalid={diagnostics.length > 0}
          onValueChange={(nextValue) => onValueChange(field, nextValue)}
          value={value}
        />
      )}
      {field.kind === "json" && field.fallbackReason && (
        <p className="schema-form__fallback-reason">{field.fallbackReason}</p>
      )}
      <FieldDiagnostics diagnostics={diagnostics} field={field} />
    </div>
  );
};
