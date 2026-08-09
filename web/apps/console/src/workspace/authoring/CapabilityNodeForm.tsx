import { useRef } from "react";
import type { InputBinding } from "../domain/draft-workspace-models.js";
import { SchemaForm } from "../schema-form/SchemaForm.js";
import type { FieldSources } from "../schema-form/schema-values.js";
import type { SchemaValueIssue } from "../schema-form/schema-values.js";

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
  readonly inputSchema?: unknown;
  readonly initialValue?: Partial<CapabilityNodeFormValue>;
  readonly initialInputValue?: unknown;
  readonly initialInputSources?: FieldSources;
  readonly diagnostics?: ReadonlyArray<SchemaValueIssue>;
  readonly onSubmit: (value: CapabilityNodeFormValue) => void | Promise<void>;
  readonly onDirtyChange?: (dirty: boolean) => void;
  readonly submitLabel?: string;
  readonly hidden?: boolean;
};

const emptySchema = { type: "object", properties: {} };

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const literalBindingsFor = (value: unknown): InputBinding[] => {
  if (!isRecord(value)) return [];
  return Object.entries(value).flatMap(([target, literal]) =>
    literal === undefined
      ? []
      : [{ target, value: { value: literal } } satisfies InputBinding],
  );
};

export const CapabilityNodeForm = ({
  capabilityName,
  inputSchema = emptySchema,
  initialValue,
  initialInputValue,
  initialInputSources,
  diagnostics,
  onSubmit,
  onDirtyChange,
  submitLabel = "Add node",
  hidden = false,
}: CapabilityNodeFormProps) => {
  const stepIdRef = useRef<HTMLInputElement>(null);
  const descriptionRef = useRef<HTMLInputElement>(null);
  const retryRef = useRef<HTMLInputElement>(null);
  const timeoutSecondsRef = useRef<HTMLInputElement>(null);
  const dirtyRef = useRef(false);

  const markDirty = (): void => {
    if (dirtyRef.current) return;
    dirtyRef.current = true;
    onDirtyChange?.(true);
  };

  return (
    <div className="authoring-form" hidden={hidden}>
      <SchemaForm
        {...(diagnostics === undefined ? {} : { diagnostics })}
        {...(initialInputSources === undefined ? {} : { initialSources: initialInputSources })}
        {...(initialInputValue === undefined ? {} : { initialValue: initialInputValue })}
        onDirtyChange={markDirty}
        onSubmit={(result) => {
          if (result.issues.length > 0) return;
          const inputBindings: InputBinding[] = [
            ...result.bindings.map((binding) => ({
              target: binding.target,
              path: binding.path,
            })),
            ...literalBindingsFor(result.value),
          ];
          void onSubmit({
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
            inputBindings,
          });
        }}
        renderBeforeFields={
          <>
            <label>
              Step id
              <input
                aria-label="Step id"
                defaultValue={initialValue?.stepId ?? ""}
                ref={stepIdRef}
                onChange={(event) => {
                  markDirty();
                }}
              />
            </label>
            <label>
              Description
              <input
                aria-label="Description"
                defaultValue={initialValue?.description ?? ""}
                ref={descriptionRef}
                onChange={(event) => {
                  markDirty();
                }}
              />
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
                  markDirty();
                }}
                type="number"
              />
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
                  markDirty();
                }}
                type="number"
              />
            </label>
          </>
        }
        submitLabel={submitLabel}
        schema={inputSchema}
      />
    </div>
  );
};
