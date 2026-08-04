import { Link, useParams } from "react-router-dom";
import type {
  DraftDiagnostic,
  DraftWorkspace,
} from "../domain/draft-workspace-models.js";
import { useDraftWorkspace } from "./useDraftWorkspace.js";

const MAX_RAW_DRAFT_CHARS = 12_000;
const TRUNCATION_MARKER = "... truncated ...";

const titleFor = (workspace: DraftWorkspace): string =>
  workspace.title?.trim() || workspace.workspaceId;

const formatStatus = (status: DraftWorkspace["status"]): string =>
  status.charAt(0).toUpperCase() + status.slice(1);

const formatValue = (value: unknown): string => {
  if (typeof value === "string") return value;
  const encoded = JSON.stringify(value);
  return encoded ?? String(value);
};

// Traverse until the display budget is exhausted so a large remote object is
// never fully materialized just to produce a clipped escape-hatch preview.
export const formatBoundedJson = (value: unknown, maxChars = MAX_RAW_DRAFT_CHARS): string => {
  const truncationMarker = TRUNCATION_MARKER.slice(0, Math.max(0, maxChars));
  const contentLimit = Math.max(0, maxChars - truncationMarker.length);
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

  const visit = (current: unknown, depth: number): void => {
    if (truncated) return;
    if (current === null || typeof current !== "object") {
      if (typeof current === "string") {
        append(JSON.stringify(current));
      } else if (typeof current === "number") {
        append(Number.isFinite(current) ? String(current) : "null");
      } else if (typeof current === "boolean") {
        append(current ? "true" : "false");
      } else {
        append("null");
      }
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
      const record = current as Record<string, unknown>;
      append("{");
      let first = true;
      for (const key in record) {
        if (!Object.prototype.hasOwnProperty.call(current, key) || truncated) continue;
        append(first ? `\n${childIndent}` : `,\n${childIndent}`);
        append(JSON.stringify(key));
        append(": ");
        visit(record[key], depth + 1);
        first = false;
      }
      if (!truncated) append(first ? "}" : `\n${indent}}`);
    }
    activeObjects.delete(current);
  };

  visit(value, 0);
  return truncated ? `${output}${truncationMarker}` : output;
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

const DraftFacts = ({ draft }: { readonly draft: DraftWorkspace }) => (
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
    ) : (
      <p>No diagnostics reported.</p>
    )}
  </section>
);

const RawDraft = ({ draft }: { readonly draft: Record<string, unknown> | null }) => (
  <details className="draft-detail__raw">
    <summary>Raw draft document</summary>
    {draft ? (
      <pre
        aria-label="Raw draft JSON, horizontally scrollable"
        role="region"
        tabIndex={0}
      >
        {formatBoundedJson(draft)}
      </pre>
    ) : (
      <p>Full draft document was not returned</p>
    )}
  </details>
);

export const DraftDetailRoute = () => {
  const { workspaceId = null } = useParams<{ workspaceId: string }>();
  const drafts = useDraftWorkspace(workspaceId);
  const draft =
    drafts.selected?.workspaceId === workspaceId ? drafts.selected : null;

  return (
    <div className="draft-detail">
      <nav aria-label="Draft breadcrumbs" className="draft-detail__breadcrumbs">
        <Link to="/console/drafts">Drafts</Link>
        <span aria-hidden="true">/</span>
        <span>{workspaceId ?? "Unknown workspace"}</span>
      </nav>

      {drafts.detailPhase === "disconnected" && (
        <p role="status">Connect a workflow server to view this draft.</p>
      )}
      {drafts.detailPhase === "loading" && <p role="status">Loading draft workspace...</p>}
      {drafts.detailPhase === "error" && (
        <p role="alert">{drafts.detailMessage ?? "Draft workspace detail failed."}</p>
      )}
      {drafts.detailPhase === "idle" && <p role="status">Select a draft workspace to inspect.</p>}

      {draft && (
        <>
          <header className="draft-detail__header">
            <p className="workspace-route-pending__eyebrow">Read-only draft</p>
            <h1>{titleFor(draft)}</h1>
            <p className="draft-detail__workspace-id">{draft.workspaceId}</p>
            <p className="draft-detail__status-line">
              <span className="draft-workspaces__status" data-status={draft.status}>
                {formatStatus(draft.status)}
              </span>
              <span>Revision {draft.revision}</span>
            </p>
          </header>

          <div className="draft-detail__panels">
            <DraftFacts draft={draft} />
            <Diagnostics diagnostics={draft.diagnostics} />
          </div>
          <RawDraft draft={draft.draft} />
        </>
      )}
    </div>
  );
};
