import {
  ArrowRight,
  Braces,
  Cable,
  CircleCheck,
  Database,
  FileLock2,
  Workflow,
} from "lucide-react";
import type { ReviewedAuthoringEvidence } from "./reviewed-authoring-evidence.js";
import { reviewedAuthoringEvidenceFor } from "./reviewed-authoring-evidence.js";

type LifecycleEvidence = Extract<
  ReviewedAuthoringEvidence,
  { readonly kind: "inventory" | "artifact" | "deployment" }
>;

type AuthoringLifecycleDiagramProps = {
  readonly evidence: LifecycleEvidence;
};

const SourceCapabilityMap = ({
  evidence,
}: {
  readonly evidence: Extract<LifecycleEvidence, { readonly kind: "inventory" }>;
}) => (
  <div
    className="authoring-lifecycle-diagram authoring-lifecycle-diagram--inventory"
    role="img"
    aria-label="Source capability map"
    data-lifecycle-diagram="inventory"
  >
    <div className="authoring-lifecycle-diagram__source-stack">
      {evidence.sources.map((source) => (
        <span key={source} className="authoring-lifecycle-diagram__source">
          <Database aria-hidden="true" />
          <code>{source}</code>
        </span>
      ))}
    </div>
    <div className="authoring-lifecycle-diagram__flow" aria-hidden="true">
      <span>Discover</span>
      <ArrowRight />
    </div>
    <section className="authoring-lifecycle-diagram__capability">
      <Braces aria-hidden="true" />
      <span>Typed capability</span>
      <strong>{evidence.capability.name}</strong>
      <dl>
        <div><dt>Input</dt><dd>{evidence.capability.inputs.join(", ")}</dd></div>
        <div><dt>Output</dt><dd>{evidence.capability.outputs.join(", ")}</dd></div>
        <div><dt>Outcome</dt><dd>{evidence.capability.outcomes.join(", ")}</dd></div>
      </dl>
    </section>
  </div>
);

const VersionedArtifactMap = ({
  evidence,
}: {
  readonly evidence: Extract<LifecycleEvidence, { readonly kind: "artifact" }>;
}) => {
  const draftEvidence = reviewedAuthoringEvidenceFor("draft");
  if (draftEvidence.kind !== "draft") {
    throw new Error("reviewed artifact diagram requires reviewed draft evidence");
  }

  return (
    <div
      className="authoring-lifecycle-diagram authoring-lifecycle-diagram--artifact"
      role="img"
      aria-label="Versioned artifact map"
      data-lifecycle-diagram="artifact"
    >
      <section className="authoring-lifecycle-diagram__draft-shape">
        <Workflow aria-hidden="true" />
        <span>Validated draft</span>
        <div>
          {draftEvidence.steps.map((step) => <code key={step}>{step}</code>)}
          <code>END</code>
        </div>
      </section>
      <div className="authoring-lifecycle-diagram__flow" aria-hidden="true">
        <span>Freeze</span>
        <ArrowRight />
      </div>
      <section className="authoring-lifecycle-diagram__artifact-object">
        <FileLock2 aria-hidden="true" />
        <span>Immutable artifact</span>
        <strong>{evidence.artifactId}</strong>
        <b>Version {evidence.version}</b>
        <div className="authoring-lifecycle-diagram__requirements">
          {evidence.requiredSources.map((source) => <code key={source}>{source}</code>)}
        </div>
      </section>
    </div>
  );
};

const DeploymentBindingMap = ({
  evidence,
}: {
  readonly evidence: Extract<LifecycleEvidence, { readonly kind: "deployment" }>;
}) => (
  <div
    className="authoring-lifecycle-diagram authoring-lifecycle-diagram--deployment"
    role="img"
    aria-label="Deployment binding map"
    data-lifecycle-diagram="deployment"
  >
    <div className="authoring-lifecycle-diagram__bindings">
      <div className="authoring-lifecycle-diagram__binding-headings" aria-hidden="true">
        <span>Requirement</span>
        <span>Configured source</span>
      </div>
      {evidence.bindings.map((binding) => (
        <div className="authoring-lifecycle-diagram__binding" key={binding.requirement}>
          <code>{binding.requirement}</code>
          <Cable aria-hidden="true" />
          <code>{binding.source}</code>
        </div>
      ))}
    </div>
    <div className="authoring-lifecycle-diagram__flow" aria-hidden="true">
      <span>Bind</span>
      <ArrowRight />
    </div>
    <section className="authoring-lifecycle-diagram__deployment-object">
      <CircleCheck aria-hidden="true" />
      <span>Deployment</span>
      <strong>{evidence.deploymentId}</strong>
      <b>{evidence.status === "runnable" ? "Runnable" : evidence.status}</b>
    </section>
  </div>
);

/** Renders fixed lifecycle mappings where graph interaction would add no value. */
export const AuthoringLifecycleDiagram = ({ evidence }: AuthoringLifecycleDiagramProps) => {
  switch (evidence.kind) {
    case "inventory":
      return <SourceCapabilityMap evidence={evidence} />;
    case "artifact":
      return <VersionedArtifactMap evidence={evidence} />;
    case "deployment":
      return <DeploymentBindingMap evidence={evidence} />;
  }
};
