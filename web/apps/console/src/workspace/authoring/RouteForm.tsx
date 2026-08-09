import { useRef } from "react";
import type { DraftDiagnostic } from "../domain/draft-workspace-models.js";

export type RouteFormValue = {
  readonly stepId: string;
  readonly outcome: string;
  readonly target: string;
};

export type RouteFormProps = {
  readonly initialValue?: Partial<RouteFormValue>;
  readonly onSubmit: (value: RouteFormValue) => void | Promise<void>;
  readonly onValueChange?: (value: RouteFormValue) => void;
  readonly diagnostics?: ReadonlyArray<DraftDiagnostic>;
  readonly onDirtyChange?: (dirty: boolean) => void;
  readonly hidden?: boolean;
  readonly submitLabel?: string;
};

export const RouteForm = ({
  initialValue,
  onSubmit,
  onValueChange,
  diagnostics = [],
  onDirtyChange,
  hidden = false,
  submitLabel = "Set route",
}: RouteFormProps) => {
  const stepIdRef = useRef<HTMLInputElement>(null);
  const outcomeRef = useRef<HTMLInputElement>(null);
  const targetRef = useRef<HTMLInputElement>(null);
  const dirtyRef = useRef(false);
  const markDirty = (): void => {
    if (dirtyRef.current) return;
    dirtyRef.current = true;
    onDirtyChange?.(true);
  };
  const readValue = (): RouteFormValue => ({
    stepId: stepIdRef.current?.value ?? "",
    outcome: outcomeRef.current?.value ?? "",
    target: targetRef.current?.value ?? "",
  });
  const notifyValueChange = (): void => {
    markDirty();
    onValueChange?.(readValue());
  };

  return (
    <form
      className="authoring-form"
      hidden={hidden}
      onSubmit={(event) => {
        event.preventDefault();
        void Promise.resolve(onSubmit(readValue())).catch(() => undefined);
      }}
    >
      <label>
        Source step
        <input
          aria-label="Source step"
          defaultValue={initialValue?.stepId ?? ""}
          ref={stepIdRef}
          onChange={(event) => {
            notifyValueChange();
          }}
        />
      </label>
      <label>
        Outcome
        <input
          aria-label="Outcome"
          defaultValue={initialValue?.outcome ?? ""}
          ref={outcomeRef}
          onChange={(event) => {
            notifyValueChange();
          }}
        />
      </label>
      <label>
        Target step
        <input
          aria-label="Target step"
          defaultValue={initialValue?.target ?? ""}
          ref={targetRef}
          onChange={(event) => {
            notifyValueChange();
          }}
        />
      </label>
      {diagnostics.map((diagnostic) => (
        <p key={`${diagnostic.code}:${diagnostic.path}`} role="alert">{diagnostic.message}</p>
      ))}
      <button type="submit">{submitLabel}</button>
    </form>
  );
};
