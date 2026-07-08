import { m } from "motion/react";
import type { InterruptContractPresentation } from "./demo-workflow-model.js";
import { SchemaApprovalSurface } from "./approval/SchemaApprovalSurface.js";
import { formatJson } from "./format.js";

type InterruptContractPreviewProps = {
  readonly contract: InterruptContractPresentation;
  readonly mode: "preview" | "approval";
  readonly hero?: boolean;
};

export const InterruptContractPreview = ({
  contract,
  mode,
  hero = false,
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
    {mode === "approval" ? (
      <SchemaApprovalSurface
        title={`${contract.kind} resume`}
        schema={contract.resumeSchema}
        payload={contract.resumePayloadPreview}
        outcomes={contract.outcomes}
        runId={contract.runId}
      />
    ) : (
      <div className="interrupt-contract-preview__schema">
        <span>Resume schema</span>
        <pre><code>{formatJson(contract.resumeSchema)}</code></pre>
      </div>
    )}
  </m.aside>
);
