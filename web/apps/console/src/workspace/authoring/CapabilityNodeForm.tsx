import { useEffect, useMemo, useRef } from "react";
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
  readonly description: string | null;
  readonly retry: number | null;
  readonly timeoutSeconds: number | null;
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
  readonly hidden?: boolean;
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
  hidden = false,
}: CapabilityNodeFormProps) => {
  const stepIdRef = useRef<HTMLInputElement>(null);
  const descriptionRef = useRef<HTMLInputElement>(null);
  const retryRef = useRef<HTMLInputElement>(null);
  const timeoutSecondsRef = useRef<HTMLInputElement>(null);
  const dirtyRef = useRef(false);
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

  const valueFor = (result: SchemaSerializationResult): CapabilityNodeFormValue => ({
    stepId: stepIdRef.current?.value ?? "",
    capabilityName,
    description: descriptionRef.current?.value.trim() || null,
    retry:
      retryRef.current?.value.trim() === ""
        ? null
        : Number(retryRef.current?.value ?? ""),
    timeoutSeconds:
      timeoutSecondsRef.current?.value.trim() === ""
        ? null
        : Number(timeoutSecondsRef.current?.value ?? ""),
    inputBindings: [
      ...result.bindings,
      ...result.literalBindings,
    ],
  });

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
          if (result.issues.length > 0) return;
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
                ref={retryRef}
                onChange={(event) => {
                  notifyMetadataChange();
                }}
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
                inputMode="numeric"
                ref={timeoutSecondsRef}
                onChange={(event) => {
                  notifyMetadataChange();
                }}
                type="number"
              />
              {metadataMessage("timeout_seconds") && <p role="alert">{metadataMessage("timeout_seconds")}</p>}
            </label>
          </>
        }
        submitLabel={submitLabel}
        schema={inputSchema}
      />
    </div>
  );
};
