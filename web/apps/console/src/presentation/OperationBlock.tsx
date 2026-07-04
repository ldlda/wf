import { m } from "motion/react";
import type { DemoEvent } from "../demo/timeline/models.js";
import { projectOperationPresentation } from "./demo-workflow-model.js";

export type OperationVariant = "expanded" | "receipt";

type OperationBlockProps = {
  readonly event: DemoEvent;
  readonly variant: OperationVariant;
  readonly openEvidence: () => void;
};

export const OperationBlock = ({
  event,
  variant,
  openEvidence,
}: OperationBlockProps) => {
  const operation = projectOperationPresentation(event);

  if (variant === "receipt") {
    return (
      <m.div
        layout
        layoutId="workflow-start-operation"
        transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}
        className="operation-receipt"
        aria-label={`${operation.operation} execution receipt`}
      >
        <div className="operation-receipt__identity">
          <span className="operation-receipt__pulse" aria-hidden="true" />
          <strong>{operation.operation}</strong>
          <span className="operation-status" data-status={operation.status}>
            {operation.status}
          </span>
        </div>
        <code>{operation.runId ?? "run unavailable"}</code>
        <small>{operation.durationMs} ms</small>
      </m.div>
    );
  }

  return (
    <m.article
      layout
      layoutId="workflow-start-operation"
      transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}
      className="operation-block operation-block--expanded"
      aria-label={`${operation.operation} operation`}
    >
      <header className="operation-block__header">
        <div>
          <span className="operation-block__kicker">Workflow operation</span>
          <strong>{operation.operation}</strong>
        </div>
        <div className="operation-block__status-group">
          <span className="operation-status" data-status={operation.status}>
            {operation.status}
          </span>
          <small>{operation.durationMs} ms</small>
        </div>
      </header>

      {operation.command && (
        <div className="operation-command">
          <span aria-hidden="true">$</span>
          <code>{operation.command}</code>
        </div>
      )}

      <dl className="operation-summary">
        <div>
          <dt>Deployment</dt>
          <dd><code>{operation.deploymentId ?? "unavailable"}</code></dd>
        </div>
        <div>
          <dt>Run</dt>
          <dd><code>{operation.runId ?? "unavailable"}</code></dd>
        </div>
        <div>
          <dt>Boundary</dt>
          <dd data-emphasis={operation.interruptKind ? "interrupt" : undefined}>
            {operation.interruptKind ?? "none"}
          </dd>
        </div>
      </dl>

      <button
        type="button"
        className="operation-block__evidence-action"
        onClick={openEvidence}
      >
        View raw evidence
        <span aria-hidden="true">-&gt;</span>
      </button>
    </m.article>
  );
};
