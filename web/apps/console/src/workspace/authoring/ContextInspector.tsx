import type { ReactNode } from "react";
import type { DraftDiagnostic, DraftWorkspace } from "../domain/draft-workspace-models.js";
import type { CapabilitySummary } from "../domain/capability-models.js";
import { projectAuthoringGraph, type WorkbenchSelection } from "./authoring-graph.js";

const MAX_RAW_DRAFT_CHARS = 12_000;
const TRUNCATION_MARKER = "... truncated ...";

type ContextInspectorProps = {
  readonly draft: DraftWorkspace;
  readonly capabilities: ReadonlyArray<CapabilitySummary>;
  readonly selection: WorkbenchSelection;
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const formatStatus = (status: DraftWorkspace["status"]): string =>
  status.charAt(0).toUpperCase() + status.slice(1);

const formatValue = (value: unknown): string => {
  if (typeof value === "string") return value;
  const encoded = JSON.stringify(value);
  return encoded ?? String(value);
};

export const formatBoundedJson = (
  value: unknown,
  maxChars = MAX_RAW_DRAFT_CHARS,
): string => {
  const truncationMarker = TRUNCATION_MARKER.slice(0, Math.max(0, maxChars));
  const contentLimit = Math.max(0, maxChars);
  let output = "";
  let truncated = false;
  const activeObjects = new WeakSet<object>();

  const append = (chunk: string): void => {
    if (truncated) return;
    if (output.length + chunk.length > contentLimit) {
      output += chunk.slice(0, Math.max(0, contentLimit - output.length));
      truncated = true;
      return;
    }
    output += chunk;
  };

  const appendJsonString = (text: string): void => {
    append('"');
    for (let index = 0; index < text.length; index++) {
      if (truncated) return;
      const code = text.charCodeAt(index);
      if (code === 0x22) append('\\"');
      else if (code === 0x5c) append("\\\\");
      else if (code < 0x20) append(`\\u${code.toString(16).padStart(4, "0")}`);
      else if (code >= 0xd800 && code <= 0xdbff) {
        const nextCode = text.charCodeAt(index + 1);
        if (nextCode >= 0xdc00 && nextCode <= 0xdfff) {
          append(text.slice(index, index + 2));
          index++;
        } else append(`\\u${code.toString(16).padStart(4, "0")}`);
      } else if (code >= 0xdc00 && code <= 0xdfff) {
        append(`\\u${code.toString(16).padStart(4, "0")}`);
      } else append(text.charAt(index));
    }
    if (!truncated) append('"');
  };

  const visit = (current: unknown, depth: number): void => {
    if (truncated) return;
    if (current === null || typeof current !== "object") {
      if (typeof current === "string") appendJsonString(current);
      else if (typeof current === "number") append(Number.isFinite(current) ? String(current) : "null");
      else if (typeof current === "boolean") append(current ? "true" : "false");
      else append("null");
      return;
    }
    if (activeObjects.has(current)) {
      append('"[Circular]"');
      return;
    }
    activeObjects.add(current);
    const indent = "  ".repeat(depth);
    const childIndent = "  ".repeat(depth + 1);
    if (Array.isArray(current)) {
      append("[");
      let first = true;
      for (const item of current) {
        if (truncated) break;
        append(first ? `\n${childIndent}` : `,\n${childIndent}`);
        visit(item, depth + 1);
        first = false;
      }
      if (!truncated) append(first ? "]" : `\n${indent}]`);
    } else {
      if (!isRecord(current)) {
        activeObjects.delete(current);
        return;
      }
      const record = current;
      append("{");
      let first = true;
      for (const key in record) {
        if (!Object.prototype.hasOwnProperty.call(record, key) || truncated) continue;
        append(first ? `\n${childIndent}` : `,\n${childIndent}`);
        appendJsonString(key);
        append(": ");
        visit(record[key], depth + 1);
        first = false;
      }
      if (!truncated) append(first ? "}" : `\n${indent}}`);
    }
    activeObjects.delete(current);
  };

  visit(value, 0);
  if (!truncated) return output;
  const markerStart = Math.max(0, contentLimit - truncationMarker.length);
  return `${output.slice(0, markerStart)}${truncationMarker}`;
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
        {diagnostics.map((diagnostic, index) => (
          <Diagnostic key={`${diagnostic.code}-${diagnostic.path}-${index}`} diagnostic={diagnostic} />
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

export const ContextInspector = ({ draft, capabilities, selection }: ContextInspectorProps) => {
  const graph = projectAuthoringGraph(draft.draft);

  let content: ReactNode;
  if (selection.kind === "canvas") {
    content = (
      <div className="draft-detail__panels">
        <DraftSummary draft={draft} />
        <Diagnostics diagnostics={draft.diagnostics} />
      </div>
    );
  } else if (selection.kind === "capability") {
    const capability = capabilities.find((item) => item.name === selection.qualifiedName);
    content = (
      <section className="authoring-inspector__selection" aria-labelledby="capability-selection-heading">
        <p className="workspace-route-pending__eyebrow">Selected capability</p>
        <h2 id="capability-selection-heading">{selection.qualifiedName}</h2>
        <p>{capability?.description ?? "Inspect this contract before configuring a new node."}</p>
        <dl className="authoring-inspector__facts">
          <Fact label="Kind" value={capability?.kind === "wrapper_artifact" ? "Wrapper artifact" : "Node spec"} />
          <Fact label="Outcomes" value={capability?.outcomes.join(", ") || "none"} />
        </dl>
      </section>
    );
  } else if (selection.kind === "edge") {
    const edge = graph.edges.find(
      (candidate) => candidate.source === selection.stepId && candidate.label === selection.outcome,
    );
    content = (
      <section className="authoring-inspector__selection" aria-labelledby="route-selection-heading">
        <p className="workspace-route-pending__eyebrow">Selected connector</p>
        <h2 id="route-selection-heading">Route inspector</h2>
        <dl className="authoring-inspector__facts">
          <Fact label="Source step" value={selection.stepId} />
          <Fact label="Outcome" value={selection.outcome || "unnamed"} />
          <Fact label="Target" value={edge?.target ?? "unknown"} />
        </dl>
      </section>
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
        {!unsupported && <p>Capability configuration will be available in the next authoring slice.</p>}
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
      <DeferredActions />
      <RawDraft draft={draft.draft} />
    </aside>
  );
};
