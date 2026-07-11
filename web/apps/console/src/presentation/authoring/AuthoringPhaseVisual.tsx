import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Database,
  FileJson,
  Link2,
  LockKeyhole,
  Workflow,
} from "lucide-react";
import type { AuthoringPhaseProjection } from "./authoring-projection.js";

type AuthoringPhaseVisualProps = {
  readonly projection: AuthoringPhaseProjection;
};

const InventoryVisual = ({ visual }: { visual: Extract<AuthoringPhaseProjection["visual"], { kind: "inventory" }> }) => (
  <section className="authoring-visual authoring-visual--inventory" aria-label="discovery evidence" data-presentation-surface="editorial">
    <div className="authoring-inventory__sources">
      {visual.sources.map((source) => (
        <div key={source}><Database aria-hidden="true" /><code>{source}</code></div>
      ))}
    </div>
    <ArrowRight className="authoring-visual__arrow" aria-hidden="true" />
    <div className="authoring-inventory__contract">
      <strong><Workflow aria-hidden="true" /> Inspected capability</strong>
      <code>{visual.capability}</code>
      <span><FileJson aria-hidden="true" />{visual.contract}</span>
    </div>
  </section>
);

const GraphVisual = ({ visual }: { visual: Extract<AuthoringPhaseProjection["visual"], { kind: "graph" }> }) => (
  <section className="authoring-visual authoring-visual--graph" aria-label="draft graph evidence" data-presentation-surface="editorial">
    <div className="authoring-graph__node"><Database aria-hidden="true" /><strong>{visual.nodes[0]}</strong></div>
    <div className="authoring-graph__edge"><span>{visual.inputBinding}</span><ArrowRight aria-hidden="true" /></div>
    <div className="authoring-graph__node"><Workflow aria-hidden="true" /><strong>{visual.nodes[1]}</strong></div>
    <div className="authoring-graph__route"><span>{visual.route}</span><ArrowRight aria-hidden="true" /></div>
    <div className="authoring-graph__end">END</div>
  </section>
);

const RepairVisual = ({ visual }: { visual: Extract<AuthoringPhaseProjection["visual"], { kind: "repair" }> }) => (
  <section className="authoring-visual authoring-visual--repair" aria-label="validation repair evidence" data-presentation-surface="editorial">
    <div className="authoring-repair__diagnostic"><AlertTriangle aria-hidden="true" /><span>Diagnostic</span><strong>{visual.diagnostic}</strong></div>
    <ArrowRight aria-hidden="true" />
    <div className="authoring-repair__correction"><Link2 aria-hidden="true" /><span>Repair</span><code>{visual.correction}</code></div>
    <div className="authoring-repair__status"><CheckCircle2 aria-hidden="true" /><strong>{visual.status}</strong></div>
  </section>
);

const ArtifactVisual = ({ visual }: { visual: Extract<AuthoringPhaseProjection["visual"], { kind: "artifact" }> }) => (
  <section className="authoring-visual authoring-visual--artifact" aria-label="artifact evidence" data-presentation-surface="editorial">
    <LockKeyhole aria-hidden="true" />
    <div><span>Immutable workflow artifact</span><strong>{visual.artifactId}</strong></div>
    <dl><div><dt>Version</dt><dd>Version {visual.version}</dd></div><div><dt>Requirements</dt><dd>{visual.requiredSources} local sources</dd></div></dl>
  </section>
);

const BindingsVisual = ({ visual }: { visual: Extract<AuthoringPhaseProjection["visual"], { kind: "bindings" }> }) => (
  <section className="authoring-visual authoring-visual--bindings" aria-label="deployment binding evidence" data-presentation-surface="editorial">
    <header><Link2 aria-hidden="true" /><div><span>Deployment</span><strong>{visual.deploymentId}</strong></div><b><CheckCircle2 aria-hidden="true" />{visual.status}</b></header>
    <div className="authoring-bindings__rows">
      {visual.bindings.map((binding) => (
        <div key={binding.requirement}><code>{binding.requirement}</code><ArrowRight aria-hidden="true" /><code>{binding.source}</code></div>
      ))}
    </div>
  </section>
);

/** Renders the factual product artifact appropriate to one authoring phase. */
export const AuthoringPhaseVisual = ({ projection }: AuthoringPhaseVisualProps) => {
  switch (projection.visual.kind) {
    case "inventory": return <InventoryVisual visual={projection.visual} />;
    case "graph": return <GraphVisual visual={projection.visual} />;
    case "repair": return <RepairVisual visual={projection.visual} />;
    case "artifact": return <ArtifactVisual visual={projection.visual} />;
    case "bindings": return <BindingsVisual visual={projection.visual} />;
  }
};
