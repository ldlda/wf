import { rebaseSchemaField, type FieldSource, type SchemaField } from "./schema-field.js";
import {
  enumOptionId,
  type FieldSources,
  type SchemaValueIssue,
} from "./schema-values.js";
import { BindingSourceControl } from "./BindingSourceControl.js";
import { encodeSchemaPath, formatTOMLPath } from "./schema-paths.js";

const EMPTY_SUGGESTIONS: ReadonlyArray<string> = [];

export type SchemaFieldControlProps = {
  readonly field: SchemaField;
  readonly value: unknown;
  readonly sources: FieldSources;
  readonly diagnostics: ReadonlyArray<SchemaValueIssue>;
  readonly onValueChange: (field: SchemaField, value: unknown) => void;
  readonly onSourceChange: (field: SchemaField, source: FieldSource) => void;
  readonly onArrayItemRemove: (field: SchemaField, index: number) => void;
  readonly sourceSuggestions?: ReadonlyArray<string>;
  readonly showSourceControl?: boolean;
  readonly idPrefix?: string;
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const pathKey = (field: SchemaField): string =>
  formatTOMLPath(field.path);

const samePath = (
  left: ReadonlyArray<string | number>,
  right: ReadonlyArray<string | number>,
): boolean => left.length === right.length && left.every((part, index) => part === right[index]);

const fieldId = (field: SchemaField, idPrefix: string): string =>
  `${idPrefix}-${encodeSchemaPath(field.path)}`;

const displayTitle = (title: string): string =>
  title.length === 0 ? "Value" : `${title.slice(0, 1).toUpperCase()}${title.slice(1)}`;

const jsonText = (value: unknown): string => {
  if (typeof value === "string") return value;
  const encoded = JSON.stringify(value, null, 2);
  return encoded ?? "";
};

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
  idPrefix,
}: {
  readonly field: SchemaField;
  readonly diagnostics: ReadonlyArray<SchemaValueIssue>;
  readonly idPrefix: string;
}) => {
  if (diagnostics.length === 0) return null;
  return (
    <div className="schema-form__diagnostics" id={`${fieldId(field, idPrefix)}-diagnostics`} role="alert">
      {diagnostics.map((diagnostic) => (
        <p key={`${formatTOMLPath(diagnostic.path)}-${diagnostic.message}`}>
          {diagnostic.message}
        </p>
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

const isPathPrefix = (
  prefix: ReadonlyArray<string | number>,
  path: ReadonlyArray<string | number>,
): boolean =>
  prefix.length <= path.length && prefix.every((part, index) => part === path[index]);

const RequiredMarker = () => (
  <>
    <span aria-hidden="true"> *</span>
    <span className="visually-hidden"> required</span>
  </>
);

const LeafControl = ({
  field,
  value,
  onValueChange,
  describedBy,
  invalid,
  idPrefix,
}: {
  readonly field: SchemaField;
  readonly value: unknown;
  readonly onValueChange: (value: unknown) => void;
  readonly describedBy: string | undefined;
  readonly invalid: boolean;
  readonly idPrefix: string;
}) => {
  const id = fieldId(field, idPrefix);
  const label = displayTitle(field.title);
  const common = {
    "aria-describedby": describedBy,
    "aria-invalid": invalid,
    "aria-required": field.required,
    id,
  };
  if (field.kind === "boolean") {
    if (field.required && !field.hasDefault) {
      const selectedValue = value === true ? "true" : value === false ? "false" : "";
      return (
        <select
          {...common}
          aria-label={label}
          onChange={(event) => {
            onValueChange(
              event.target.value === "true"
                ? true
                : event.target.value === "false"
                  ? false
                  : undefined,
            );
          }}
          value={selectedValue}
        >
          <option value="">Choose true or false</option>
          <option value="true">true</option>
          <option value="false">false</option>
        </select>
      );
    }
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
    const selectedIndex = field.enumValues.findIndex((option) => option === value);
    const selectedOption = selectedIndex >= 0 ? field.enumValues[selectedIndex] : undefined;
    const selectedValue = selectedOption === undefined
      ? ""
      : enumOptionId(selectedOption, selectedIndex);
    return (
      <select
        {...common}
        aria-label={label}
        onChange={(event) => {
          const optionIndex = field.enumValues.findIndex(
            (option, index) => enumOptionId(option, index) === event.target.value,
          );
          const option = optionIndex >= 0 ? field.enumValues[optionIndex] : undefined;
          onValueChange(option);
        }}
        value={selectedValue}
      >
        <option value="">Choose {label.toLowerCase()}</option>
        {field.enumValues.map((option, index) => (
          <option key={enumOptionId(option, index)} value={enumOptionId(option, index)}>
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
  onArrayItemRemove,
  sourceSuggestions = EMPTY_SUGGESTIONS,
  showSourceControl = true,
  idPrefix = "schema-field",
}: SchemaFieldControlProps) => {
  const id = fieldId(field, idPrefix);
  const descriptionId = field.description ? `${id}-description` : undefined;
  const ownDiagnostics = diagnostics.filter((diagnostic) => samePath(diagnostic.path, field.path));
  const diagnosticsId = ownDiagnostics.length > 0 ? `${id}-diagnostics` : undefined;
  const fallbackReasonId = field.kind === "json" && field.fallbackReason ? `${id}-fallback` : undefined;
  const describedBy = [descriptionId, fallbackReasonId, diagnosticsId].filter(Boolean).join(" ") || undefined;

  if (field.kind === "object") {
    const objectValue = isRecord(value) ? value : {};
    return (
      <fieldset aria-describedby={describedBy} aria-required={field.required} className="schema-form__group">
        <legend>
          {displayTitle(field.title)}
          {field.required && <RequiredMarker />}
        </legend>
        {field.description && <p id={descriptionId}>{field.description}</p>}
        {field.children.map((child) => (
          <SchemaFieldControl
            diagnostics={diagnostics.filter((diagnostic) => isPathPrefix(child.path, diagnostic.path))}
            field={child}
            key={pathKey(child)}
            onArrayItemRemove={onArrayItemRemove}
            onSourceChange={onSourceChange}
            onValueChange={onValueChange}
            sourceSuggestions={sourceSuggestions}
            sources={sources}
            showSourceControl={showSourceControl}
            idPrefix={idPrefix}
            value={objectValue[child.key]}
          />
        ))}
        <FieldDiagnostics
          diagnostics={ownDiagnostics}
          field={field}
          idPrefix={idPrefix}
        />
      </fieldset>
    );
  }

  if (field.kind === "array") {
    const arrayValue = Array.isArray(value) ? value : [];
    return (
      <fieldset aria-describedby={describedBy} aria-required={field.required} className="schema-form__group schema-form__array">
        <legend>
          {displayTitle(field.title)}
          {field.required && <RequiredMarker />}
        </legend>
        {field.description && <p id={descriptionId}>{field.description}</p>}
        {arrayValue.map((itemValue, index) => {
          const itemField = field.item
            ? { ...rebaseSchemaField(field.item, [...field.path, index]), title: arrayItemTitle(field, index) }
            : null;
          if (!itemField) return null;
          return (
            <div className="schema-form__array-item" key={pathKey(itemField)}>
              <SchemaFieldControl
                diagnostics={diagnostics.filter((diagnostic) => isPathPrefix(itemField.path, diagnostic.path))}
                field={itemField}
                onSourceChange={onSourceChange}
                onArrayItemRemove={onArrayItemRemove}
                onValueChange={onValueChange}
                sourceSuggestions={sourceSuggestions}
                sources={sources}
                showSourceControl={showSourceControl}
                idPrefix={idPrefix}
                value={itemValue}
              />
              <button
                aria-label={`Remove ${arrayItemTitle(field, index).toLowerCase()}`}
                className="schema-form__secondary-action"
                onClick={() => onArrayItemRemove(field, index)}
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
          diagnostics={ownDiagnostics}
          field={field}
          idPrefix={idPrefix}
        />
      </fieldset>
    );
  }

  const source: FieldSource = showSourceControl
    ? sources[pathKey(field)] ?? { mode: "literal", value }
    : { mode: "literal", value };
  return (
    <div className="schema-form__field">
      <FieldLabel field={field} id={id} />
      {field.description && <p id={descriptionId}>{field.description}</p>}
      {showSourceControl && (
        <BindingSourceControl
          field={field}
          idPrefix={idPrefix}
          literalValue={value}
          onChange={(nextSource) => onSourceChange(field, nextSource)}
          source={source}
          suggestions={sourceSuggestions}
        />
      )}
      {source.mode === "literal" && (
        <LeafControl
          describedBy={describedBy}
          field={field}
          invalid={ownDiagnostics.length > 0}
          idPrefix={idPrefix}
          onValueChange={(nextValue) => onValueChange(field, nextValue)}
          value={value}
        />
      )}
      {field.kind === "json" && field.fallbackReason && (
        <p className="schema-form__fallback-reason" id={fallbackReasonId}>
          {field.fallbackReason}
        </p>
      )}
      <FieldDiagnostics diagnostics={ownDiagnostics} field={field} idPrefix={idPrefix} />
    </div>
  );
};
