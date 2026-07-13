import {
  AlertTriangle,
  CheckCircle2,
  Database,
  Link2,
  LockKeyhole,
  Route,
  Workflow,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import type { PreparedLifecycleStepProjection } from "./authoring-projection.js";
import { AuthoringLifecycleDiagram } from "./AuthoringLifecycleDiagram.js";
import { AuthoringWorkflowDiagram } from "./AuthoringWorkflowDiagram.js";
import { reviewedAuthoringEvidenceFor } from "./reviewed-authoring-evidence.js";

type Evidence = PreparedLifecycleStepProjection["evidence"];
type EvidenceOf<Kind extends Evidence["kind"]> = Extract<Evidence, { readonly kind: Kind }>;

type ResultHeaderProps = {
  readonly icon: LucideIcon;
  readonly label: string;
  readonly status: string;
  readonly revision?: number;
};

const ResultHeader = ({ icon: Icon, label, status, revision }: ResultHeaderProps) => (
  <header className="authoring-result__header">
    <div className="authoring-result__heading">
      <Icon aria-hidden="true" />
      <div>
        <span>{label}</span>
        {revision !== undefined && <code>Revision {revision}</code>}
      </div>
    </div>
    <strong>{status}</strong>
  </header>
);

const EvidenceRows = ({
  rows,
}: {
  readonly rows: readonly { readonly label: string; readonly value: ReactNode }[];
}) => (
  <dl className="authoring-result__rows">
    {rows.map(({ label, value }) => (
      <div key={label}>
        <dt>{label}</dt>
        <dd>{value}</dd>
      </div>
    ))}
  </dl>
);

const RouteList = ({ routes }: { readonly routes: readonly string[] }) => (
  <section className="authoring-result__list-section">
    <h3>Routes</h3>
    <ul>
      {routes.map((route) => <li key={route}><code>{route}</code></li>)}
    </ul>
  </section>
);

const ResultRoot = ({
  kind,
  label,
  children,
}: {
  readonly kind: Evidence["kind"];
  readonly label: string;
  readonly children: ReactNode;
}) => (
  <section
    className={`authoring-visual authoring-result authoring-result--${kind}`}
    aria-label={label}
    data-authoring-result={kind}
    data-scrollport="bounded-result"
    data-scroll-bound="viewport-relative"
    data-presentation-surface="editorial"
    data-visual-role="primary"
  >
    {children}
  </section>
);

const ResultComposition = ({
  diagramKind,
  diagram,
  receiptLabel,
  receipt,
}: {
  readonly diagramKind: string;
  readonly diagram: ReactNode;
  readonly receiptLabel: string;
  readonly receipt: ReactNode;
}) => (
  <div className="authoring-result__composition">
    <div
      className="authoring-result__diagram"
      data-testid="authoring-primary-diagram"
      data-diagram-kind={diagramKind}
    >
      {diagram}
    </div>
    <aside className="authoring-result__receipt" aria-label={receiptLabel}>
      {receipt}
    </aside>
  </div>
);

const InventoryResult = ({ evidence }: { readonly evidence: EvidenceOf<"inventory"> }) => (
  <ResultRoot kind={evidence.kind} label="source inventory result">
    <ResultHeader icon={Database} label="SOURCE INVENTORY" status={`${evidence.sourceCount} TOTAL SOURCES`} />
    <ResultComposition
      diagramKind="inventory"
      diagram={<AuthoringLifecycleDiagram evidence={evidence} />}
      receiptLabel="source inventory technical receipt"
      receipt={(
        <>
          <h3>Configured local sources ({evidence.sources.length})</h3>
          <EvidenceRows
            rows={[
              { label: "Inventory", value: <strong>{evidence.sourceCount} total inventory sources</strong> },
              { label: "Configured", value: <strong>{evidence.sources.length} configured local source IDs</strong> },
              { label: "Inputs", value: <code>{evidence.capability.inputs.join(", ")}</code> },
              { label: "Outputs", value: <code>{evidence.capability.outputs.join(", ")}</code> },
              { label: "Outcomes", value: <code>{evidence.capability.outcomes.join(", ")}</code> },
            ]}
          />
        </>
      )}
    />
  </ResultRoot>
);

const DraftResult = ({ evidence }: { readonly evidence: EvidenceOf<"draft"> }) => (
  <ResultRoot kind={evidence.kind} label="draft structure result">
    <ResultHeader icon={Workflow} label="VALID DRAFT" status="Valid" revision={evidence.revision} />
    <ResultComposition
      diagramKind="workflow-draft"
      diagram={<AuthoringWorkflowDiagram mode="draft" evidence={evidence} />}
      receiptLabel="draft structure technical receipt"
      receipt={(
        <>
          <EvidenceRows
            rows={[
              { label: "Workspace", value: <code>{evidence.workspaceId}</code> },
              { label: "Steps", value: evidence.stepCount },
              { label: "Routes", value: evidence.routeCount },
            ]}
          />
          <RouteList routes={evidence.routes} />
        </>
      )}
    />
  </ResultRoot>
);

const DiagnosticResult = ({ evidence }: { readonly evidence: EvidenceOf<"diagnostic"> }) => (
  <ResultRoot kind={evidence.kind} label="draft validation diagnostic">
    <ResultHeader icon={AlertTriangle} label="INVALID DRAFT" status="Invalid" revision={evidence.revision} />
    <ResultComposition
      diagramKind="workflow-diagnostic"
      diagram={<AuthoringWorkflowDiagram mode="diagnostic" evidence={evidence} />}
      receiptLabel="draft validation technical receipt"
      receipt={(
        <>
          <EvidenceRows
            rows={[
              { label: "Diagnostic", value: <code>{evidence.diagnostic.code}</code> },
              { label: "Path", value: <code>{evidence.diagnostic.path}</code> },
              { label: "Message", value: evidence.diagnostic.message },
            ]}
          />
          <p className="authoring-result__explanation">{evidence.diagnostic.explanation}</p>
          <section className="authoring-result__fault-injection" role="note" aria-label={evidence.faultInjection.label}>
            <span>{evidence.faultInjection.label}</span>
            <code>{evidence.faultInjection.command}</code>
            <p>Valid revision {evidence.faultInjection.fromRevision} became invalid revision {evidence.faultInjection.toRevision}.</p>
          </section>
        </>
      )}
    />
  </ResultRoot>
);

const RepairResult = ({ evidence }: { readonly evidence: EvidenceOf<"repair"> }) => {
  const priorEvidence = reviewedAuthoringEvidenceFor("diagnose");
  if (priorEvidence.kind !== "diagnostic") {
    throw new Error("reviewed repair context has an unexpected shape");
  }

  return (
    <ResultRoot kind={evidence.kind} label="route repair result">
      <ResultHeader icon={Route} label="ROUTE REPAIR" status="Valid" revision={evidence.toRevision} />
      <ResultComposition
        diagramKind="workflow-repair"
        diagram={<AuthoringWorkflowDiagram mode="repair" evidence={evidence} />}
        receiptLabel="route repair technical receipt"
        receipt={(
          <>
            <aside className="authoring-result__prior" role="note" aria-label="prior validation diagnostic">
              <span>Prior validation</span>
              <code>{priorEvidence.diagnostic.code} · {priorEvidence.diagnostic.path}</code>
              <p>{priorEvidence.diagnostic.message}</p>
            </aside>
            <div data-result-primary="true">
              <EvidenceRows
                rows={[
                  { label: "Command", value: <code>{evidence.command}</code> },
                  { label: "Result", value: <strong>Valid</strong> },
                  { label: "Diagnostics", value: <strong>{evidence.diagnosticCount} diagnostics</strong> },
                ]}
              />
            </div>
          </>
        )}
      />
    </ResultRoot>
  );
};

const ArtifactResult = ({ evidence }: { readonly evidence: EvidenceOf<"artifact"> }) => (
  <ResultRoot kind={evidence.kind} label="immutable artifact result">
    <ResultHeader icon={LockKeyhole} label="IMMUTABLE ARTIFACT" status="Immutable" />
    <ResultComposition
      diagramKind="artifact"
      diagram={<AuthoringLifecycleDiagram evidence={evidence} />}
      receiptLabel="immutable artifact technical receipt"
      receipt={(
        <EvidenceRows
          rows={[
            { label: "Required sources", value: `${evidence.requiredSources.length} configured local sources` },
          ]}
        />
      )}
    />
  </ResultRoot>
);

const DeploymentResult = ({ evidence }: { readonly evidence: EvidenceOf<"deployment"> }) => (
  <ResultRoot kind={evidence.kind} label="runnable deployment result">
    <ResultHeader icon={Link2} label="RUNNABLE DEPLOYMENT" status={`${evidence.bindings.length} BINDINGS`} />
    <ResultComposition
      diagramKind="deployment"
      diagram={<AuthoringLifecycleDiagram evidence={evidence} />}
      receiptLabel="runnable deployment technical receipt"
      receipt={(
        <EvidenceRows
          rows={[
            { label: "Bindings", value: <strong>{evidence.bindings.length} valid bindings</strong> },
            { label: "Next", value: <span className="authoring-result__status"><CheckCircle2 aria-hidden="true" />Ready for a persisted run</span> },
          ]}
        />
      )}
    />
  </ResultRoot>
);

/** Renders one audience-facing product result from the reviewed evidence union. */
export const AuthoringPhaseVisual = ({ projection }: { readonly projection: PreparedLifecycleStepProjection }) => {
  switch (projection.evidence.kind) {
    case "inventory":
      return <InventoryResult evidence={projection.evidence} />;
    case "draft":
      return <DraftResult evidence={projection.evidence} />;
    case "diagnostic":
      return <DiagnosticResult evidence={projection.evidence} />;
    case "repair":
      return <RepairResult evidence={projection.evidence} />;
    case "artifact":
      return <ArtifactResult evidence={projection.evidence} />;
    case "deployment":
      return <DeploymentResult evidence={projection.evidence} />;
  }
};
