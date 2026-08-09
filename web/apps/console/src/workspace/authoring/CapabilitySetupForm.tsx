import { useState, type FormEvent } from "react";
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
  const [description, setDescription] = useState(initialText(initialValue.description));
  const [retry, setRetry] = useState(
    initialValue.retry === null || initialValue.retry === undefined ? "" : String(initialValue.retry),
  );
  const [timeoutSeconds, setTimeoutSeconds] = useState(
    initialValue.timeoutSeconds === null || initialValue.timeoutSeconds === undefined
      ? ""
      : String(initialValue.timeoutSeconds),
  );
  const [touched, setTouched] = useState<ReadonlySet<SetupField>>(() => new Set());
  const [issues, setIssues] = useState<ReadonlyArray<string>>([]);

  const touch = (field: SetupField): void => {
    setTouched((current) => current.has(field) ? current : new Set([...current, field]));
    onDirtyChange?.(true);
  };

  const submit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    const nextIssues: string[] = [];
    const patch: {
      description?: string | null;
      retry?: number | null;
      timeoutSeconds?: number | null;
    } = {};

    if (touched.has("description")) {
      if (description.trim() === "") {
        if (initialValue.description !== undefined && initialValue.description !== null) {
          patch.description = null;
        }
      } else {
        patch.description = description.trim();
      }
    }

    if (touched.has("retry")) {
      if (retry.trim() === "") {
        if (existingNumber(initialValue.retry)) patch.retry = null;
      } else {
        const parsed = Number(retry);
        if (!Number.isFinite(parsed) || !Number.isInteger(parsed) || parsed < 0) {
          nextIssues.push(
            !Number.isInteger(parsed) && Number.isFinite(parsed)
              ? "Retry must be a whole number."
              : "Retry must be at least 0.",
          );
        } else {
          patch.retry = parsed;
        }
      }
    }

    if (touched.has("timeoutSeconds")) {
      if (timeoutSeconds.trim() === "") {
        if (existingNumber(initialValue.timeoutSeconds)) patch.timeoutSeconds = null;
      } else {
        const parsed = Number(timeoutSeconds);
        if (!Number.isFinite(parsed) || parsed <= 0) {
          nextIssues.push("Timeout must be greater than 0.");
        } else {
          patch.timeoutSeconds = parsed;
        }
      }
    }

    setIssues(nextIssues);
    if (nextIssues.length > 0) return;
    void Promise.resolve(onSubmit(patch)).catch(() => undefined);
  };

  return (
    <form className="schema-form authoring-form" noValidate onSubmit={submit}>
      <fieldset className="schema-form__group">
        <legend>Setup</legend>
        <label>
          Description
          <input
            aria-describedby={issueMessage(diagnostics, "description") ? "setup-description-diagnostic" : undefined}
            aria-label="Description"
            onChange={(event) => { touch("description"); setDescription(event.target.value); }}
            type="text"
            value={description}
          />
          {issueMessage(diagnostics, "description") && (
            <p id="setup-description-diagnostic" role="alert">{issueMessage(diagnostics, "description")}</p>
          )}
        </label>
        <label>
          Retry
          <input
            aria-describedby={issueMessage(diagnostics, "retry") ? "setup-retry-diagnostic" : undefined}
            aria-label="Retry"
            inputMode="numeric"
            min={0}
            onChange={(event) => { touch("retry"); setRetry(event.target.value); }}
            step={1}
            type="number"
            value={retry}
          />
          {issueMessage(diagnostics, "retry") && (
            <p id="setup-retry-diagnostic" role="alert">{issueMessage(diagnostics, "retry")}</p>
          )}
        </label>
        <label>
          Timeout seconds
          <input
            aria-describedby={issueMessage(diagnostics, "timeoutSeconds") ? "setup-timeout-diagnostic" : undefined}
            aria-label="Timeout seconds"
            inputMode="decimal"
            min="0.000001"
            onChange={(event) => { touch("timeoutSeconds"); setTimeoutSeconds(event.target.value); }}
            step="any"
            type="number"
            value={timeoutSeconds}
          />
          {issueMessage(diagnostics, "timeoutSeconds") && (
            <p id="setup-timeout-diagnostic" role="alert">{issueMessage(diagnostics, "timeoutSeconds")}</p>
          )}
        </label>
        {issues.length > 0 && (
          <div className="schema-form__diagnostics" role="alert">
            {issues.map((issue) => <p key={issue}>{issue}</p>)}
          </div>
        )}
      </fieldset>
      <button type="submit">{submitLabel}</button>
    </form>
  );
};
