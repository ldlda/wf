import { useEffect, useId, useState } from "react";
import type {
  AuthoringPathOption,
  AuthoringPathOrigin,
  AuthoringPathUse,
} from "../domain/authoring-contract-models.js";

export type AuthoringPathPickerProps = {
  readonly options: ReadonlyArray<AuthoringPathOption>;
  readonly uses: AuthoringPathUse | ReadonlyArray<AuthoringPathUse>;
  readonly value: string;
  readonly onChange: (value: string) => void;
  readonly label: string;
  readonly allowCustom?: boolean;
};

type OptionGroup = {
  readonly origin: AuthoringPathOrigin;
  readonly label: string;
};

const OPTION_GROUPS: ReadonlyArray<OptionGroup> = [
  { origin: "workflow_input", label: "Workflow input" },
  { origin: "workflow_state", label: "State" },
  { origin: "step_output", label: "Step output" },
  { origin: "runtime_context", label: "Runtime context" },
  { origin: "workflow_output", label: "Workflow output" },
  { origin: "step_input", label: "Step input" },
];

const safeId = (value: string): string => value.replaceAll(/[^a-zA-Z0-9_-]/g, "-");

const optionText = (option: AuthoringPathOption): string =>
  [option.label, option.path, option.description].filter(Boolean).join(" ").toLocaleLowerCase();

const normalizedUses = (
  uses: AuthoringPathUse | ReadonlyArray<AuthoringPathUse>,
): ReadonlySet<AuthoringPathUse> => new Set(Array.isArray(uses) ? uses : [uses]);

export const AuthoringPathPicker = ({
  options,
  uses,
  value,
  onChange,
  label,
  allowCustom = false,
}: AuthoringPathPickerProps) => {
  const id = safeId(useId());
  const searchId = `${id}-search`;
  const customId = `${id}-custom`;
  const [search, setSearch] = useState("");
  const [customValue, setCustomValue] = useState(value);
  const requestedUses = normalizedUses(uses);
  const normalizedSearch = search.trim().toLocaleLowerCase();

  useEffect(() => {
    setCustomValue(value);
  }, [value]);

  const visibleOptions = options.filter((option) =>
    normalizedSearch === "" || optionText(option).includes(normalizedSearch),
  );

  return (
    <section aria-labelledby={`${id}-heading`} className="authoring-path-picker">
      <h3 id={`${id}-heading`}>{label}</h3>
      <label htmlFor={searchId}>Search {label}</label>
      <input
        id={searchId}
        onChange={(event) => setSearch(event.target.value)}
        placeholder="Search labels or paths"
        type="search"
        value={search}
      />
      <div aria-label={`${label} options`} className="authoring-path-picker__options">
        {OPTION_GROUPS.map((group) => {
          const groupOptions = visibleOptions.filter((option) => option.origin === group.origin);
          if (groupOptions.length === 0) return null;
          return (
            <fieldset className="authoring-path-picker__group" key={group.origin}>
              <legend>{group.label}</legend>
              <div className="authoring-path-picker__list">
                {groupOptions.map((option, optionIndex) => {
                  const compatible = option.uses.some((use) => requestedUses.has(use));
                  const reasonId = `${id}-${safeId(group.origin)}-${optionIndex}-description`;
                  const availabilityReason = option.availability === "conditional"
                    ? option.reason ?? "Conditionally available; verify this path at runtime."
                    : option.reason;
                  const description = [
                    availabilityReason,
                    ...(compatible ? [] : ["Not available for this field."]),
                  ].filter((part): part is string => part !== undefined).join(" ");
                  return (
                    <button
                      aria-describedby={description === "" ? undefined : reasonId}
                      aria-pressed={option.path === value}
                      className="authoring-path-picker__option"
                      disabled={!compatible}
                      key={option.path}
                      onClick={() => {
                        setCustomValue(option.path);
                        onChange(option.path);
                      }}
                      type="button"
                    >
                      <strong>{option.label}</strong>
                      <code>{option.path}</code>
                      {option.description !== undefined && <span>{option.description}</span>}
                      {option.required && <small>Required</small>}
                      {description !== "" && <small id={reasonId}>{description}</small>}
                    </button>
                  );
                })}
              </div>
            </fieldset>
          );
        })}
        {visibleOptions.length === 0 && <p>No matching paths.</p>}
      </div>
      {allowCustom && (
        <details className="authoring-path-picker__advanced">
          <summary>Advanced</summary>
          <label htmlFor={customId}>Custom {label}</label>
          <input
            id={customId}
            onChange={(event) => {
              setCustomValue(event.target.value);
              onChange(event.target.value);
            }}
            type="text"
            value={customValue}
          />
        </details>
      )}
    </section>
  );
};
