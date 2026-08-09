import { useRef } from "react";

export type RouteFormValue = {
  readonly stepId: string;
  readonly outcome: string;
  readonly target: string;
};

export type RouteFormProps = {
  readonly initialValue?: Partial<RouteFormValue>;
  readonly onSubmit: (value: RouteFormValue) => void | Promise<void>;
  readonly onDirtyChange?: (dirty: boolean) => void;
  readonly hidden?: boolean;
  readonly submitLabel?: string;
};

export const RouteForm = ({
  initialValue,
  onSubmit,
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

  return (
    <form
      className="authoring-form"
      hidden={hidden}
      onSubmit={(event) => {
        event.preventDefault();
        void onSubmit({
          stepId: stepIdRef.current?.value ?? "",
          outcome: outcomeRef.current?.value ?? "",
          target: targetRef.current?.value ?? "",
        });
      }}
    >
      <label>
        Source step
        <input
          aria-label="Source step"
          defaultValue={initialValue?.stepId ?? ""}
          ref={stepIdRef}
          onChange={(event) => {
            markDirty();
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
            markDirty();
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
            markDirty();
          }}
        />
      </label>
      <button type="submit">{submitLabel}</button>
    </form>
  );
};
