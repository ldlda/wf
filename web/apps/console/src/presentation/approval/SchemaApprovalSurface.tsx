import { buildSchemaApprovalModel } from "./schema-approval-model.js";

export type SchemaApprovalSurfaceProps = {
  readonly title: string;
  readonly schema: unknown;
  readonly payload: unknown;
  readonly outcomes: ReadonlyArray<string>;
  readonly runId: string | null;
  readonly state?: "ready" | "submitted" | "cancelled";
  readonly onSubmit?: (() => void) | undefined;
  readonly onCancel?: (() => void) | undefined;
};

export const SchemaApprovalSurface = ({
  title,
  schema,
  payload,
  outcomes,
  runId,
  state = "ready",
  onSubmit,
  onCancel,
}: SchemaApprovalSurfaceProps) => {
  const model = buildSchemaApprovalModel({ schema, payload, outcomes });
  const isResolved = state !== "ready";

  return (
    <section className="schema-approval-surface" role="group" aria-label={title} data-state={state}>
      <header className="schema-approval-surface__header">
        <span>Schema-backed decision</span>
        <strong>{title}</strong>
        <code>{runId ?? "run unavailable"}</code>
      </header>

      <div className="schema-approval-surface__body">
        {model.hasExplicitFields ? (
          <dl className="schema-approval-surface__fields">
            {model.fields.map((field) => (
              <div key={field.name} className="schema-approval-surface__field" data-kind={field.kind}>
                <dt>
                  <span>{field.label}</span>
                  {field.required ? <small>required</small> : <small>optional</small>}
                </dt>
                <dd>
                  <code>{field.valuePreview ?? "not provided"}</code>
                  {field.description ? <p>{field.description}</p> : null}
                </dd>
              </div>
            ))}
          </dl>
        ) : (
          <div className="schema-approval-surface__loose">
            <p>No additional resume fields are declared by this schema.</p>
            <dl>
              {model.payloadPreview.map((entry) => (
                <div key={entry.key}>
                  <dt>{entry.key}</dt>
                  <dd><code>{entry.value}</code></dd>
                </div>
              ))}
            </dl>
          </div>
        )}
      </div>

      <footer className="schema-approval-surface__actions">
        {isResolved ? (
          <strong>Outcome: {state}</strong>
        ) : (
          <>
            <button type="button" onClick={onSubmit} disabled={!onSubmit}>
              Submit
            </button>
            <button type="button" onClick={onCancel} disabled={!onCancel}>
              Cancel
            </button>
          </>
        )}
        <span>{model.outcomes.join(" / ")}</span>
      </footer>
    </section>
  );
};
