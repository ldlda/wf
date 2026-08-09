import type { ReactNode } from "react";
import type { DraftDiagnostic, DraftWorkspace } from "../domain/draft-workspace-models.js";
import type { CapabilitySummary } from "../domain/capability-models.js";
import { projectAuthoringGraph, type WorkbenchSelection } from "./authoring-graph.js";
import { withDiagnosticKeys } from "./diagnostic-key.js";
import { formatBoundedJson } from "./format-bounded-json.js";
import { CapabilityNodeForm } from "./CapabilityNodeForm.js";
import { RouteForm } from "./RouteForm.js";
import type { DraftAuthoringController } from "./useDraftAuthoring.js";

type ContextInspectorProps = {
  readonly draft: DraftWorkspace;
  readonly capabilities: ReadonlyArray<CapabilitySummary>;
  readonly selection: WorkbenchSelection;
  readonly controller: DraftAuthoringController;
};

const formatStatus = (status: DraftWorkspace["status"]): string =>
  status.charAt(0).toUpperCase() + status.slice(1);

const formatValue = (value: unknown): string => {
  if (typeof value === "string") return value;
  const encoded = JSON.stringify(value);
  return encoded ?? String(value);
};

const Fact = ({ label, value }: { readonly label: string; readonly value: string }) => (
  <div>
    <dt>{label}</dt>
    <dd>{value}</dd>
  </div>
);

const Diagnostic = ({ diagnostic }: { readonly diagnostic: DraftDiagnostic }) => (
  <li className="draft-detail__diagnostic">
    <dl>
      <Fact label="Code" value={diagnostic.code} />
      <Fact label="Path" value={diagnostic.path} />
      <Fact label="Message" value={diagnostic.message} />
      <Fact label="Step id" value={diagnostic.stepId ?? "none"} />
      <Fact label="Repair hint" value={diagnostic.repairHint ?? "none"} />
    </dl>
  </li>
);

const DraftSummary = ({ draft }: { readonly draft: DraftWorkspace }) => (
  <section aria-labelledby="draft-detail-summary-heading" className="draft-detail__panel">
    <h2 id="draft-detail-summary-heading">Draft summary</h2>
    <dl className="draft-detail__facts">
      <Fact label="Status" value={formatStatus(draft.status)} />
      <Fact label="Revision" value={`Revision ${draft.revision}`} />
      <Fact label="Start step" value={formatValue(draft.summary.start)} />
      <Fact label="Step count" value={String(draft.summary.stepCount)} />
      <Fact label="Route count" value={String(draft.summary.routeCount)} />
    </dl>
    <h3>Step ids</h3>
    <ul className="draft-detail__steps">
      {draft.summary.steps.map((stepId) => <li key={stepId}>{stepId}</li>)}
    </ul>
  </section>
);

const Diagnostics = ({ diagnostics }: { readonly diagnostics: ReadonlyArray<DraftDiagnostic> }) => (
  <section aria-labelledby="draft-detail-diagnostics-heading" className="draft-detail__panel">
    <h2 id="draft-detail-diagnostics-heading">Diagnostics</h2>
    {diagnostics.length > 0 ? (
      <ol className="draft-detail__diagnostics">
        {withDiagnosticKeys(diagnostics).map(({ diagnostic, key }) => (
          <Diagnostic key={key} diagnostic={diagnostic} />
        ))}
      </ol>
    ) : <p>No diagnostics reported.</p>}
  </section>
);

const RawDraft = ({ draft }: { readonly draft: DraftWorkspace["draft"] }) => (
  <details className="draft-detail__raw">
    <summary>Raw draft document</summary>
    {draft ? (
      <pre aria-label="Raw draft JSON, horizontally scrollable" role="region" tabIndex={0}>
        {formatBoundedJson(draft)}
      </pre>
    ) : <p>Full draft document was not returned</p>}
  </details>
);

const DeferredActions = () => (
  <section className="authoring-inspector__deferred" aria-labelledby="deferred-actions-heading">
    <h3 id="deferred-actions-heading">Deferred actions</h3>
    <div className="authoring-inspector__deferred-actions">
      {[
        "Undo — Later",
        "Redo — Later",
        "Delete node — Later",
        "Delete route — Later",
        "Add other step — Later",
        "Create artifact — Later",
      ].map((label) => <button disabled key={label} type="button">{label}</button>)}
    </div>
  </section>
);

export const ContextInspector = ({ draft, capabilities, selection, controller }: ContextInspectorProps) => {
  const graph = projectAuthoringGraph(draft.draft);

  let content: ReactNode;
  if (selection.kind === "canvas") {
    content = (
      <div className="draft-detail__panels">
        <DraftSummary draft={draft} />
        <Diagnostics diagnostics={draft.diagnostics} />
        <button onClick={() => void controller.validate()} type="button">
          Validate draft
        </button>
      </div>
    );
  } else if (selection.kind === "capability") {
    const capability = capabilities.find((item) => item.name === selection.qualifiedName);
    content = (
      <>
        <section className="authoring-inspector__selection" aria-labelledby="capability-selection-heading">
          <p className="workspace-route-pending__eyebrow">Selected capability</p>
          <h2 id="capability-selection-heading">{selection.qualifiedName}</h2>
          <p>{capability?.description ?? "Configure this capability before adding it."}</p>
          <dl className="authoring-inspector__facts">
            <Fact label="Kind" value={capability?.kind === "wrapper_artifact" ? "Wrapper artifact" : "Node spec"} />
            <Fact label="Outcomes" value={capability?.outcomes.join(", ") || "none"} />
          </dl>
        </section>
        <CapabilityNodeForm
          key={`capability:${selection.qualifiedName}:${controller.resetGeneration}`}
          capabilityName={selection.qualifiedName}
          onDirtyChange={controller.markDirty}
          onSubmit={controller.addCapability}
        />
      </>
    );
  } else if (selection.kind === "edge") {
    const edge = graph.edges.find(
      (candidate) => candidate.source === selection.stepId && candidate.label === selection.outcome,
    );
    content = (
      <>
        <section className="authoring-inspector__selection" aria-labelledby="route-selection-heading">
          <p className="workspace-route-pending__eyebrow">Selected connector</p>
          <h2 id="route-selection-heading">Route inspector</h2>
          <dl className="authoring-inspector__facts">
            <Fact label="Source step" value={selection.stepId} />
            <Fact label="Outcome" value={selection.outcome || "unnamed"} />
            <Fact label="Target" value={edge?.target ?? "unknown"} />
          </dl>
        </section>
        <RouteForm
          key={`edge:${selection.stepId}:${selection.outcome}:${controller.resetGeneration}`}
          initialValue={{ stepId: selection.stepId, outcome: selection.outcome, target: edge?.target ?? "" }}
          onSubmit={controller.setRoute}
          onDirtyChange={controller.markDirty}
        />
      </>
    );
  } else {
    const node = graph.nodes.find((candidate) => candidate.id === selection.nodeId);
    const unsupported = node?.data.kind === "unsupported";
    content = (
      <section className="authoring-inspector__selection" aria-labelledby="node-selection-heading">
        <p className="workspace-route-pending__eyebrow">Selected step</p>
        <h2 id="node-selection-heading">{selection.nodeId}</h2>
        <dl className="authoring-inspector__facts">
          <Fact label="Kind" value={node?.data.kind ?? "unknown"} />
          <Fact label="Reference" value={node?.data.nodeRef ?? "none"} />
        </dl>
        {unsupported && <p role="status">Read-only: unsupported step kind.</p>}
        {!unsupported && (
          <CapabilityNodeForm
            key={`node:${selection.nodeId}:${controller.resetGeneration}`}
            capabilityName={node?.data.nodeRef ?? selection.nodeId}
            initialValue={{ stepId: selection.nodeId }}
            onDirtyChange={controller.markDirty}
            onSubmit={controller.updateCapability}
          />
        )}
      </section>
    );
  }

  return (
    <aside aria-label="Context inspector" className="context-inspector" role="region">
      <div className="context-inspector__heading">
        <p className="workspace-route-pending__eyebrow">Selection context</p>
        <h2>Inspector</h2>
      </div>
      {content}
      {controller.phase === "saving" && <p role="status">Saving canonical draft...</p>}
      {controller.phase === "error" && <p role="alert">{controller.message ?? "Draft mutation failed."}</p>}
      {controller.phase === "conflict" && (
        <section aria-label="Revision conflict" className="authoring-inspector__conflict">
          <p role="alert">{controller.message ?? "The draft changed on the server."}</p>
          <button onClick={() => void controller.reload()} type="button">Reload server draft</button>
          <button onClick={() => void controller.reapply()} type="button">Reapply local form</button>
        </section>
      )}
      <DeferredActions />
      <RawDraft draft={draft.draft} />
    </aside>
  );
};
