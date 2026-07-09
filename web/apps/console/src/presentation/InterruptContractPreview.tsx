import { m } from "motion/react";
import type { InterruptContractPresentation } from "./demo-workflow-model.js";
import type { DemoApprovalActions } from "./demo-approval-actions.js";
import { SchemaApprovalSurface } from "./approval/SchemaApprovalSurface.js";
import { formatJson } from "./format.js";

type InterruptContractPreviewProps = {
  readonly contract: InterruptContractPresentation;
  readonly mode: "preview" | "approval";
  readonly hero?: boolean;
  readonly approvalActions?: DemoApprovalActions | undefined;
};

const titleForKind = (kind: string): string => `${kind.replaceAll("_", " ")} resume`;

export const InterruptContractPreview = ({
  contract,
  mode,
  hero = false,
  approvalActions,
}: InterruptContractPreviewProps) => (
  <m.aside
    className="interrupt-contract-preview"
    data-mode={mode}
    data-hero={hero ? "true" : "false"}
    initial={{ opacity: 0, x: 10 }}
    animate={{ opacity: 1, x: 0 }}
    transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
    aria-label="typed interrupt contract"
  >
    <header>
      <span>{mode === "approval" ? "Operator decision" : "Execution paused"}</span>
      <strong>{contract.kind}</strong>
    </header>
    {mode === "preview" ? (
      <dl>
        <div>
          <dt>Persisted run</dt>
          <dd><code>{contract.runId ?? "unavailable"}</code></dd>
        </div>
        <div>
          <dt>Resume outcomes</dt>
          <dd>{contract.outcomes.join(" / ")}</dd>
        </div>
      </dl>
    ) : null}
    {mode === "approval" ? (
      <SchemaApprovalSurface
        title={titleForKind(contract.kind)}
        schema={contract.resumeSchema}
        payload={contract.resumePayloadPreview}
        outcomes={contract.outcomes}
        runId={contract.runId}
        state={approvalActions?.state ?? "ready"}
        onSubmit={approvalActions?.canSubmit ? () => void approvalActions.submit() : undefined}
        onCancel={approvalActions?.canCancel ? () => void approvalActions.cancel() : undefined}
      />
    ) : (
      <div className="interrupt-contract-preview__schema">
        <span>Resume schema</span>
        <pre><code>{formatJson(contract.resumeSchema)}</code></pre>
      </div>
    )}
  </m.aside>
);
