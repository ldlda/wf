import type { ReactNode } from "react";
import type { DraftDiagnostic, DraftWorkspace } from "../domain/draft-workspace-models.js";
import type { CapabilityDetail, CapabilitySummary } from "../domain/capability-models.js";
import { projectAuthoringGraph, type WorkbenchSelection } from "./authoring-graph.js";
import { withDiagnosticKeys } from "./diagnostic-key.js";
import { formatBoundedJson } from "../domain/format-bounded-json.js";
import { CapabilityNodeForm } from "./CapabilityNodeForm.js";
import { SelectedCapabilityInspector } from "./SelectedCapabilityInspector.js";
import { RouteForm } from "./RouteForm.js";
import type { DraftAuthoringController } from "./useDraftAuthoring.js";

type ContextInspectorProps = {
  readonly draft: DraftWorkspace;
  readonly capabilities: ReadonlyArray<CapabilitySummary>;
  readonly selection: WorkbenchSelection;
  readonly controller: DraftAuthoringController;
  readonly capabilityDetail: CapabilityDetail | null;
  readonly capabilityDetailPhase: "disconnected" | "loading" | "ready" | "error";
  readonly capabilityDetailMessage: string | null;
};

const formatStatus = (status: DraftWorkspace["status"]): string =>
  status.charAt(0).toUpperCase() + status.slice(1);

const formatValue = (value: unknown): string => {
  if (typeof value === "string") return value;
  const encoded = JSON.stringify(value);
  return encoded ?? String(value);
};

const diagnosticParts = (path: string): string[] => {
  const normalized = path.startsWith("/")
    ? path.slice(1).replaceAll("~1", "/").replaceAll("~0", "~")
    : path.replace(/\[([^\]]+)\]/g, ".$1");
  return normalized.split(".").filter((part) => part.length > 0);
};

const routeDiagnostics = (
  diagnostics: ReadonlyArray<DraftDiagnostic>,
  selection: Extract<WorkbenchSelection, { readonly kind: "edge" }>,
): ReadonlyArray<DraftDiagnostic> => diagnostics.filter((diagnostic) => {
  if (diagnostic.stepId !== null && diagnostic.stepId !== selection.stepId) return false;
  const parts = diagnosticParts(diagnostic.path);
  return parts.includes("routes") || diagnostic.stepId === selection.stepId;
});

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
  <section
    aria-describedby="deferred-actions-description"
    aria-labelledby="deferred-actions-heading"
    className="authoring-inspector__deferred"
  >
    <h3 id="deferred-actions-heading">Deferred actions</h3>
    <p id="deferred-actions-description">
      These actions are not available in this workbench yet.
    </p>
    <div className="authoring-inspector__deferred-actions">
      {[
        "Undo — Later",
        "Redo — Later",
        "Delete node — Later",
        "Delete route — Later",
        "Add other step — Later",
        "Create artifact — Later",
      ].map((label) => (
        <button
          aria-describedby="deferred-actions-description"
          aria-disabled="true"
          key={label}
          onClick={(event) => event.preventDefault()}
          type="button"
        >
          {label}
        </button>
      ))}
    </div>
  </section>
);

export const ContextInspector = ({
  draft,
  capabilities,
  selection,
  controller,
  capabilityDetail,
  capabilityDetailPhase,
  capabilityDetailMessage,
}: ContextInspectorProps) => {
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
        {capabilityDetailPhase === "loading" && <p role="status">Loading capability schema...</p>}
        {capabilityDetailPhase === "error" && (
          <p role="alert">{capabilityDetailMessage ?? "Capability schema failed to load."}</p>
        )}
        {capabilityDetailPhase === "ready" && capabilityDetail !== null && (
          <CapabilityNodeForm
            key={`capability:${selection.qualifiedName}:${controller.resetGeneration}`}
            capabilityName={selection.qualifiedName}
            diagnostics={[]}
            inputSchema={capabilityDetail.inputSchema}
            onDirtyChange={controller.markDirty}
            onSubmit={controller.addCapability}
            onValueChange={(value) => controller.rememberCapabilityForm("add", value)}
            routeOutcomes={capabilityDetail.outcomes}
          />
        )}
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
          diagnostics={routeDiagnostics(draft.diagnostics, selection)}
          onDirtyChange={controller.markDirty}
          onValueChange={controller.rememberRouteForm}
        />
      </>
    );
  } else {
    const node = graph.nodes.find((candidate) => candidate.id === selection.nodeId);
    content = (
      <SelectedCapabilityInspector
        key={selection.nodeId}
        capabilityDetail={capabilityDetail}
        capabilityDetailMessage={capabilityDetailMessage}
        capabilityDetailPhase={capabilityDetailPhase}
        controller={controller}
        draft={draft}
        nodeRef={node?.data.nodeRef ?? null}
        stepId={selection.nodeId}
        {...(node?.data.kind ? { nodeKind: node.data.kind } : {})}
      />
    );
  }

  return (
    <aside aria-label="Context inspector" className="context-inspector" role="region">
      <div className="context-inspector__heading">
        <p className="workspace-route-pending__eyebrow">Selection context</p>
        <h2>Inspector</h2>
      </div>
      {content}
      {selection.kind !== "canvas" && draft.diagnostics.length > 0 && (
        <Diagnostics diagnostics={draft.diagnostics} />
      )}
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
