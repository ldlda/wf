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

const StringList = ({ label, items }: { readonly label: string; readonly items: readonly string[] }) => (
  <section className="authoring-result__list-section">
    <h3>{label}</h3>
    <ul>
      {items.map((item) => (
        <li key={item}><code>{item}</code></li>
      ))}
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
    data-presentation-surface="editorial"
    data-visual-role="primary"
  >
    {children}
  </section>
);

const InventoryResult = ({ evidence }: { readonly evidence: EvidenceOf<"inventory"> }) => (
  <ResultRoot kind={evidence.kind} label="source inventory result">
    <ResultHeader
      icon={Database}
      label="SOURCE INVENTORY"
      status={`${evidence.sourceCount} TOTAL SOURCES`}
    />
    <div className="authoring-result__body">
      <EvidenceRows
        rows={[
          {
            label: "Inventory",
            value: <strong>{evidence.sourceCount} total inventory sources</strong>,
          },
          {
            label: "Configured local sources",
            value: <strong>{evidence.sources.length} configured local source IDs</strong>,
          },
        ]}
      />
      <StringList label={`Configured local sources (${evidence.sources.length})`} items={evidence.sources} />
      <section className="authoring-result__contract">
        <h3>Capability contract</h3>
        <EvidenceRows
          rows={[
            { label: "Capability", value: <code>{evidence.capability.name}</code> },
            { label: "Inputs", value: <code>{evidence.capability.inputs.join(", ")}</code> },
            { label: "Outputs", value: <code>{evidence.capability.outputs.join(", ")}</code> },
            { label: "Outcomes", value: <code>{evidence.capability.outcomes.join(", ")}</code> },
          ]}
        />
      </section>
    </div>
  </ResultRoot>
);

const DraftResult = ({ evidence }: { readonly evidence: EvidenceOf<"draft"> }) => (
  <ResultRoot kind={evidence.kind} label="draft structure result">
    <ResultHeader icon={Workflow} label="VALID DRAFT" status="Valid" revision={evidence.revision} />
    <div className="authoring-result__body">
      <EvidenceRows
        rows={[
          { label: "Workspace", value: <code>{evidence.workspaceId}</code> },
          { label: "Steps", value: evidence.stepCount },
          { label: "Routes", value: evidence.routeCount },
        ]}
      />
      <StringList label="Steps" items={evidence.steps} />
      <StringList label="Routes" items={evidence.routes} />
    </div>
  </ResultRoot>
);

const DiagnosticResult = ({ evidence }: { readonly evidence: EvidenceOf<"diagnostic"> }) => (
  <ResultRoot kind={evidence.kind} label="draft validation diagnostic">
    <ResultHeader
      icon={AlertTriangle}
      label="INVALID DRAFT"
      status={evidence.status === "invalid" ? "Invalid" : evidence.status}
      revision={evidence.revision}
    />
    <div className="authoring-result__body" data-result-primary="true">
      <EvidenceRows
        rows={[
          { label: "Diagnostic", value: <code>{evidence.diagnostic.code}</code> },
          { label: "Path", value: <code>{evidence.diagnostic.path}</code> },
          { label: "Message", value: evidence.diagnostic.message },
        ]}
      />
      <p className="authoring-result__explanation">{evidence.diagnostic.explanation}</p>
    </div>
  </ResultRoot>
);

const RepairResult = ({ evidence }: { readonly evidence: EvidenceOf<"repair"> }) => {
  // The repair record keeps the successful result compact; prior invalid context
  // comes from the same reviewed catalog and is never presented as a new result.
  const priorEvidence = reviewedAuthoringEvidenceFor("diagnose");
  if (priorEvidence.kind !== "diagnostic") {
    throw new Error("reviewed repair context has an unexpected shape");
  }

  return (
    <ResultRoot kind={evidence.kind} label="route repair result">
      <ResultHeader
        icon={Route}
        label="ROUTE REPAIR"
        status={evidence.status === "valid" ? "Valid" : evidence.status}
        revision={evidence.toRevision}
      />
      <aside className="authoring-result__prior" role="note" aria-label="prior validation diagnostic">
        <span>Prior validation</span>
        <code>{priorEvidence.diagnostic.code} · {priorEvidence.diagnostic.path}</code>
        <p>{priorEvidence.diagnostic.message}</p>
      </aside>
      <div className="authoring-result__body" data-result-primary="true">
        <EvidenceRows
          rows={[
            { label: "Command", value: <code>{evidence.command}</code> },
            { label: "Result", value: <strong>Valid</strong> },
            { label: "Diagnostics", value: <strong>0 diagnostics</strong> },
          ]}
        />
      </div>
    </ResultRoot>
  );
};

const ArtifactResult = ({ evidence }: { readonly evidence: EvidenceOf<"artifact"> }) => (
  <ResultRoot kind={evidence.kind} label="immutable artifact result">
    <ResultHeader icon={LockKeyhole} label="IMMUTABLE ARTIFACT" status="Immutable" />
    <div className="authoring-result__body">
      <EvidenceRows
        rows={[
          { label: "Artifact", value: <code>{evidence.artifactId}</code> },
          { label: "Version", value: <strong>Version {evidence.version}</strong> },
          { label: "Required sources", value: `${evidence.requiredSources.length} configured local sources` },
        ]}
      />
      <StringList label="Required local sources" items={evidence.requiredSources} />
    </div>
  </ResultRoot>
);

const DeploymentResult = ({ evidence }: { readonly evidence: EvidenceOf<"deployment"> }) => (
  <ResultRoot kind={evidence.kind} label="runnable deployment result">
    <ResultHeader
      icon={Link2}
      label="RUNNABLE DEPLOYMENT"
      status={evidence.status === "runnable" ? "Runnable" : evidence.status}
    />
    <div className="authoring-result__body">
      <EvidenceRows
        rows={[{ label: "Deployment", value: <code>{evidence.deploymentId}</code> }]}
      />
      <section className="authoring-result__list-section">
        <h3>Bindings</h3>
        <ul>
          {evidence.bindings.map((binding) => (
            <li key={binding.requirement}>
              <code>{binding.requirement}</code>
              <span aria-hidden="true">-&gt;</span>
              <code>{binding.source}</code>
            </li>
          ))}
        </ul>
      </section>
      <p className="authoring-result__status"><CheckCircle2 aria-hidden="true" /> Ready for a persisted run</p>
    </div>
  </ResultRoot>
);

/** Renders one audience-facing product result from the reviewed evidence union. */
export const AuthoringPhaseVisual = ({
  projection,
}: {
  readonly projection: PreparedLifecycleStepProjection;
}) => {
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
