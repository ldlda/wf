import type { FieldSource, SchemaField } from "./schema-field.js";

export type BindingSourceControlProps = {
  readonly field: SchemaField;
  readonly source: FieldSource;
  readonly onChange: (source: FieldSource) => void;
  readonly suggestions?: ReadonlyArray<string>;
};

const fieldKey = (field: SchemaField): string =>
  field.path.length === 0 ? "root" : field.path.map(String).join("-");

const displayTitle = (title: string): string =>
  title.length === 0 ? "Value" : `${title.slice(0, 1).toUpperCase()}${title.slice(1)}`;

export const BindingSourceControl = ({
  field,
  source,
  onChange,
  suggestions = [],
}: BindingSourceControlProps) => {
  const key = fieldKey(field);
  const literalId = `${key}-literal`;
  const bindId = `${key}-bind`;
  const sourceId = `${key}-source-path`;
  const listId = `${key}-source-suggestions`;

  return (
    <fieldset className="schema-form__source">
      <legend>Value source</legend>
      <div className="schema-form__source-options">
        <label htmlFor={literalId}>
          <input
            checked={source.mode === "literal"}
            id={literalId}
            name={`${key}-source-mode`}
            onChange={() => onChange({ mode: "literal", value: source.mode === "literal" ? source.value : "" })}
            type="radio"
          />
          Literal
        </label>
        <label htmlFor={bindId}>
          <input
            checked={source.mode === "bind"}
            id={bindId}
            name={`${key}-source-mode`}
            onChange={() => onChange({ mode: "bind", sourcePath: "input." })}
            type="radio"
          />
          Bind
        </label>
      </div>
      {source.mode === "bind" && (
        <div className="schema-form__source-path">
          <label htmlFor={sourceId}>Source path for {displayTitle(field.title)}</label>
          <input
            aria-describedby={suggestions.length > 0 ? listId : undefined}
            id={sourceId}
            list={suggestions.length > 0 ? listId : undefined}
            onChange={(event) => onChange({ mode: "bind", sourcePath: event.target.value })}
            type="text"
            value={source.sourcePath}
          />
          {suggestions.length > 0 && (
            <datalist id={listId}>
              {suggestions.map((suggestion) => <option key={suggestion} value={suggestion} />)}
            </datalist>
          )}
        </div>
      )}
    </fieldset>
  );
};
