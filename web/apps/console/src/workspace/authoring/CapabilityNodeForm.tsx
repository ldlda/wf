import { useEffect, useMemo, useRef, useState, type RefObject } from "react";
import type { InputBinding } from "../domain/draft-workspace-models.js";
import { SchemaForm } from "../schema-form/SchemaForm.js";
import { normalizeSchema } from "../schema-form/schema-field.js";
import {
  serializeSchemaValues,
  type FieldSources,
  type SchemaSerializationResult,
  type SchemaValueIssue,
} from "../schema-form/schema-values.js";

export type CapabilityNodeFormValue = {
  readonly stepId: string;
  readonly capabilityName: string;
  readonly description?: string | null;
  readonly retry?: number | null;
  readonly timeoutSeconds?: number | null;
  readonly inputBindings: ReadonlyArray<InputBinding> | null;
  readonly inputMap?: Record<string, string> | null;
  readonly routes?: Record<string, string> | null;
  readonly bindOutputs?: Record<string, string>;
};

export type CapabilityNodeFormProps = {
  readonly capabilityName: string;
  readonly inputSchema: unknown;
  readonly initialValue?: Partial<CapabilityNodeFormValue>;
  readonly initialInputValue?: unknown;
  readonly initialInputSources?: FieldSources;
  readonly diagnostics?: ReadonlyArray<SchemaValueIssue>;
  readonly metadataDiagnostics?: ReadonlyArray<SchemaValueIssue>;
  readonly onSubmit: (value: CapabilityNodeFormValue) => void | Promise<void>;
  readonly onValueChange?: (value: CapabilityNodeFormValue) => void;
  readonly onDirtyChange?: (dirty: boolean) => void;
  readonly submitLabel?: string;
  readonly stepIdReadOnly?: boolean;
  readonly routeOutcomes?: ReadonlyArray<string>;
  readonly hidden?: boolean;
};

const optionalNumber = (
  ref: RefObject<HTMLInputElement | null>,
  initial: number | null | undefined,
  touched: boolean,
): number | null | undefined => {
  const raw = ref.current?.value.trim() ?? "";
  if (raw !== "") return Number(raw);
  return touched && typeof initial === "number" ? null : undefined;
};

export const CapabilityNodeForm = ({
  capabilityName,
  inputSchema,
  initialValue,
  initialInputValue,
  initialInputSources,
  diagnostics,
  metadataDiagnostics = [],
  onSubmit,
  onValueChange,
  onDirtyChange,
  submitLabel = "Add node",
  stepIdReadOnly = false,
  routeOutcomes = [],
  hidden = false,
}: CapabilityNodeFormProps) => {
  const stepIdRef = useRef<HTMLInputElement>(null);
  const descriptionRef = useRef<HTMLInputElement>(null);
  const retryRef = useRef<HTMLInputElement>(null);
  const timeoutSecondsRef = useRef<HTMLInputElement>(null);
  const routeTargetRefs = useRef(new Map<string, HTMLInputElement>());
  const dirtyRef = useRef(false);
  const descriptionTouchedRef = useRef(false);
  const retryTouchedRef = useRef(false);
  const timeoutTouchedRef = useRef(false);
  const [metadataIssues, setMetadataIssues] = useState<ReadonlyArray<string>>([]);
  const initialSchemaResult = useMemo(
    () => serializeSchemaValues(
      normalizeSchema(inputSchema),
      initialInputValue,
      initialInputSources,
    ),
    [initialInputSources, initialInputValue, inputSchema],
  );
  const schemaResultRef = useRef<SchemaSerializationResult | null>(null);
  useEffect(() => {
    schemaResultRef.current = initialSchemaResult;
  }, [initialSchemaResult]);

  const valueFor = (result: SchemaSerializationResult): CapabilityNodeFormValue => {
    const description = descriptionRef.current?.value.trim() ?? "";
    const retry = optionalNumber(retryRef, initialValue?.retry, retryTouchedRef.current);
    const timeoutSeconds = optionalNumber(
      timeoutSecondsRef,
      initialValue?.timeoutSeconds,
      timeoutTouchedRef.current,
    );
    return {
      stepId: stepIdRef.current?.value ?? "",
      capabilityName,
      ...(description !== ""
        ? { description }
        : descriptionTouchedRef.current && typeof initialValue?.description === "string"
          ? { description: null }
          : {}),
      ...(retry === undefined ? {} : { retry }),
      ...(timeoutSeconds === undefined ? {} : { timeoutSeconds }),
      inputBindings: [
        ...result.bindings,
        ...result.literalBindings,
      ],
      ...(routeOutcomes.length > 0
        ? {
            routes: Object.fromEntries(
              routeOutcomes.map((outcome) => [
                outcome,
                routeTargetRefs.current.get(outcome)?.value.trim() || "__end__",
              ]),
            ),
          }
        : {}),
    };
  };

  const validateMetadata = (): ReadonlyArray<string> => {
    const issues: string[] = [];
    const retry = retryRef.current?.value.trim() ?? "";
    if (retry !== "") {
      const value = Number(retry);
      if (!Number.isFinite(value) || !Number.isInteger(value) || value < 0) {
        issues.push("Retry must be a whole number at least 0.");
      }
    }
    const timeout = timeoutSecondsRef.current?.value.trim() ?? "";
    if (timeout !== "") {
      const value = Number(timeout);
      if (!Number.isFinite(value) || value <= 0) {
        issues.push("Timeout must be greater than 0.");
      }
    }
    return issues;
  };

  const notifyValueChange = (result: SchemaSerializationResult): void => {
    schemaResultRef.current = result;
    onValueChange?.(valueFor(result));
  };

  const metadataMessage = (field: string): string | null =>
    metadataDiagnostics.find((diagnostic) => diagnostic.path.at(-1) === field)?.message ?? null;

  const markDirty = (): void => {
    if (dirtyRef.current) return;
    dirtyRef.current = true;
    onDirtyChange?.(true);
  };

  const notifyMetadataChange = (): void => {
    markDirty();
    onValueChange?.(valueFor(schemaResultRef.current ?? initialSchemaResult));
  };

  return (
    <div className="authoring-form" hidden={hidden}>
      <SchemaForm
        {...(diagnostics === undefined ? {} : { diagnostics })}
        {...(initialInputSources === undefined ? {} : { initialSources: initialInputSources })}
        {...(initialInputValue === undefined ? {} : { initialValue: initialInputValue })}
        onDirtyChange={markDirty}
        onValueChange={notifyValueChange}
        onSubmit={(result) => {
          const nextMetadataIssues = validateMetadata();
          setMetadataIssues(nextMetadataIssues);
          if (result.issues.length > 0 || nextMetadataIssues.length > 0) return;
          notifyValueChange(result);
          void Promise.resolve(onSubmit(valueFor(result))).catch(() => undefined);
        }}
        renderBeforeFields={
          <>
            <label>
              Step id
              <input
                aria-label="Step id"
                defaultValue={initialValue?.stepId ?? ""}
                readOnly={stepIdReadOnly}
                ref={stepIdRef}
                onChange={() => {
                  notifyMetadataChange();
                }}
              />
              {metadataMessage("stepId") && <p role="alert">{metadataMessage("stepId")}</p>}
            </label>
            <label>
              Description
              <input
                aria-label="Description"
                defaultValue={initialValue?.description ?? ""}
                ref={descriptionRef}
                onChange={(event) => {
                  descriptionTouchedRef.current = true;
                  notifyMetadataChange();
                }}
              />
              {metadataMessage("desc") && <p role="alert">{metadataMessage("desc")}</p>}
            </label>
            <label>
              Retry
              <input
                aria-label="Retry"
                defaultValue={
                  initialValue?.retry === null || initialValue?.retry === undefined
                    ? ""
                    : String(initialValue.retry)
                }
                inputMode="numeric"
                min={0}
                ref={retryRef}
                onChange={(event) => {
                  retryTouchedRef.current = true;
                  notifyMetadataChange();
                }}
                step={1}
                type="number"
              />
              {metadataMessage("retry") && <p role="alert">{metadataMessage("retry")}</p>}
            </label>
            <label>
              Timeout seconds
              <input
                aria-label="Timeout seconds"
                defaultValue={
                  initialValue?.timeoutSeconds === null || initialValue?.timeoutSeconds === undefined
                    ? ""
                    : String(initialValue.timeoutSeconds)
                }
                inputMode="decimal"
                min="0.000001"
                ref={timeoutSecondsRef}
                onChange={(event) => {
                  timeoutTouchedRef.current = true;
                  notifyMetadataChange();
                }}
                step="any"
                type="number"
              />
              {metadataMessage("timeout_seconds") && <p role="alert">{metadataMessage("timeout_seconds")}</p>}
            </label>
            {routeOutcomes.length > 0 && (
              <fieldset className="authoring-form__routes">
                <legend>Outcome routes</legend>
                <p>Choose where each declared outcome continues. New routes default to the workflow end.</p>
                {routeOutcomes.map((outcome) => (
                  <label key={outcome}>
                    {outcome}
                    <input
                      aria-label={`Route target for ${outcome}`}
                      defaultValue={initialValue?.routes?.[outcome] ?? "__end__"}
                      onChange={notifyMetadataChange}
                      ref={(element) => {
                        if (element === null) routeTargetRefs.current.delete(outcome);
                        else routeTargetRefs.current.set(outcome, element);
                      }}
                    />
                  </label>
                ))}
              </fieldset>
            )}
          </>
        }
        submitLabel={submitLabel}
        schema={inputSchema}
      />
      {metadataIssues.length > 0 && (
        <div className="schema-form__diagnostics" role="alert">
          {metadataIssues.map((issue) => <p key={issue}>{issue}</p>)}
        </div>
      )}
    </div>
  );
};
