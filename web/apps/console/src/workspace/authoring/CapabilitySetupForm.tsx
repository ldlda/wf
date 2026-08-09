import { useId, useRef, useState, type FormEvent } from "react";
import type { DraftDiagnostic } from "../domain/draft-workspace-models.js";
import type { SchemaValueIssue } from "../schema-form/schema-values.js";
import type { CapabilitySetupPatch } from "./selected-step-dataflow.js";

export type CapabilitySetupFormValue = CapabilitySetupPatch;

export type CapabilitySetupFormProps = {
  readonly initialValue?: Partial<CapabilitySetupPatch>;
  readonly diagnostics?: ReadonlyArray<SchemaValueIssue | DraftDiagnostic>;
  readonly onSubmit: (value: CapabilitySetupFormValue) => void | Promise<void>;
  readonly onDirtyChange?: (dirty: boolean) => void;
  readonly submitLabel?: string;
};

type SetupField = "description" | "retry" | "timeoutSeconds";

const fieldName = (field: SetupField): string =>
  field === "timeoutSeconds" ? "timeout_seconds" : field === "description" ? "desc" : "retry";

const issueMessage = (
  diagnostics: ReadonlyArray<SchemaValueIssue | DraftDiagnostic>,
  field: SetupField,
): string | null => diagnostics.find((diagnostic) => {
  const path = diagnostic.path;
  const last = typeof path === "string" ? path.split(".").at(-1) : path.at(-1);
  return last === fieldName(field) || last === field;
})?.message ?? null;

const initialText = (value: string | null | undefined): string => value ?? "";

const existingNumber = (value: number | null | undefined): boolean => typeof value === "number";

export const CapabilitySetupForm = ({
  initialValue = {},
  diagnostics = [],
  onSubmit,
  onDirtyChange,
  submitLabel = "Save setup",
}: CapabilitySetupFormProps) => {
  const [description, setDescription] = useState(() => initialText(initialValue.description));
  const [retry, setRetry] = useState(() =>
    initialValue.retry === null || initialValue.retry === undefined ? "" : String(initialValue.retry),
  );
  const [timeoutSeconds, setTimeoutSeconds] = useState(() =>
    initialValue.timeoutSeconds === null || initialValue.timeoutSeconds === undefined
      ? ""
      : String(initialValue.timeoutSeconds),
  );
  const touchedRef = useRef<ReadonlySet<SetupField>>(new Set());
  const [issues, setIssues] = useState<Readonly<Partial<Record<SetupField, string>>>>({});
  const formId = useId();

  const controlId = (field: SetupField): string => `${formId}-${field}`;
  const errorId = (field: SetupField): string => `${controlId(field)}-error`;
  const diagnosticFor = (field: SetupField): string | null =>
    issues[field] ?? issueMessage(diagnostics, field);

  const touch = (field: SetupField): void => {
    if (!touchedRef.current.has(field)) {
      touchedRef.current = new Set([...touchedRef.current, field]);
    }
    onDirtyChange?.(true);
  };

  const submit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    const nextIssues: Partial<Record<SetupField, string>> = {};
    const patch: {
      description?: string | null;
      retry?: number | null;
      timeoutSeconds?: number | null;
    } = {};

    if (touchedRef.current.has("description")) {
      if (description.trim() === "") {
        if (initialValue.description !== undefined && initialValue.description !== null) {
          patch.description = null;
        }
      } else {
        patch.description = description.trim();
      }
    }

    if (touchedRef.current.has("retry")) {
      if (retry.trim() === "") {
        if (existingNumber(initialValue.retry)) patch.retry = null;
      } else {
        const parsed = Number(retry);
        if (!Number.isFinite(parsed) || !Number.isInteger(parsed) || parsed < 0) {
          nextIssues.retry =
            !Number.isInteger(parsed) && Number.isFinite(parsed)
              ? "Retry must be a whole number."
              : "Retry must be at least 0.";
        } else {
          patch.retry = parsed;
        }
      }
    }

    if (touchedRef.current.has("timeoutSeconds")) {
      if (timeoutSeconds.trim() === "") {
        if (existingNumber(initialValue.timeoutSeconds)) patch.timeoutSeconds = null;
      } else {
        const parsed = Number(timeoutSeconds);
        if (!Number.isFinite(parsed) || parsed <= 0) {
          nextIssues.timeoutSeconds = "Timeout must be greater than 0.";
        } else if (!Number.isInteger(parsed)) {
          nextIssues.timeoutSeconds = "Timeout must be a whole number greater than 0.";
        } else {
          patch.timeoutSeconds = parsed;
        }
      }
    }

    setIssues(nextIssues);
    if (Object.keys(nextIssues).length > 0) return;
    void Promise.resolve(onSubmit(patch)).catch(() => undefined);
  };

  return (
    <form className="schema-form authoring-form" noValidate onSubmit={submit}>
      <fieldset className="schema-form__group">
        <legend>Setup</legend>
        <label>
          Description
          <input
            aria-describedby={diagnosticFor("description") ? errorId("description") : undefined}
            aria-label="Description"
            aria-invalid={diagnosticFor("description") !== null}
            id={controlId("description")}
            onChange={(event) => { touch("description"); setDescription(event.target.value); }}
            type="text"
            value={description}
          />
          {diagnosticFor("description") && (
            <p id={errorId("description")} role="alert">{diagnosticFor("description")}</p>
          )}
        </label>
        <label>
          Retry
          <input
            aria-describedby={diagnosticFor("retry") ? errorId("retry") : undefined}
            aria-label="Retry"
            aria-invalid={diagnosticFor("retry") !== null}
            id={controlId("retry")}
            inputMode="numeric"
            min={0}
            onChange={(event) => { touch("retry"); setRetry(event.target.value); }}
            step={1}
            type="number"
            value={retry}
          />
          {diagnosticFor("retry") && (
            <p id={errorId("retry")} role="alert">{diagnosticFor("retry")}</p>
          )}
        </label>
        <label>
          Timeout seconds
          <input
            aria-describedby={diagnosticFor("timeoutSeconds") ? errorId("timeoutSeconds") : undefined}
            aria-label="Timeout seconds"
            aria-invalid={diagnosticFor("timeoutSeconds") !== null}
            id={controlId("timeoutSeconds")}
            inputMode="numeric"
            min={1}
            onChange={(event) => { touch("timeoutSeconds"); setTimeoutSeconds(event.target.value); }}
            step={1}
            type="number"
            value={timeoutSeconds}
          />
          {diagnosticFor("timeoutSeconds") && (
            <p id={errorId("timeoutSeconds")} role="alert">{diagnosticFor("timeoutSeconds")}</p>
          )}
        </label>
      </fieldset>
      <button type="submit">{submitLabel}</button>
    </form>
  );
};
