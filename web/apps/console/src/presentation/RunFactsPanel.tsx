import { Fragment } from "react";
import type { DemoRunFacts } from "./demo-run-facts.js";

type RunInputFactsProps = {
  readonly facts: DemoRunFacts;
};

export const RunInputFacts = ({ facts }: RunInputFactsProps) => (
  <div className="run-facts-card">
    <h3>Workflow input</h3>
    <dl className="run-facts-dl">
      <dt>Selected documents</dt>
      <dd>
        <ul className="run-facts-list">
          {facts.input.selectedDocuments.map((doc) => (
            <li key={doc}>{doc}</li>
          ))}
        </ul>
      </dd>
      <dt>Board path</dt>
      <dd>{facts.input.boardPath}</dd>
    </dl>
  </div>
);

type RunFactsPriority = "summary" | "report";

const displayPayloadValue = (value: unknown): string => {
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "boolean") return value ? "true" : "false";
  if (value === null || value === undefined) return "none";
  return String(value);
};

export const InterruptPayloadFacts = ({ facts }: RunInputFactsProps) => (
  <div className="run-facts-card run-facts-card--interrupt">
    <h3>Interrupt payload</h3>
    <dl className="run-facts-dl run-facts-dl--inline">
      <dt>Kind</dt><dd>{facts.interrupt.kind}</dd>
      <dt>Typed</dt><dd>{facts.interrupt.typed ? "yes" : "no"}</dd>
      <dt>Outcomes</dt><dd>{facts.interrupt.outcomes.join(", ")}</dd>
    </dl>
    <div className="run-facts-scroll-region run-facts-scroll-region--report" role="region" aria-label="interrupt report markdown">
      <pre className="run-facts-markdown-preview">{facts.interrupt.reportMarkdownPreview}</pre>
    </div>
    <ul className="run-facts-list run-facts-list--issues">
      {facts.interrupt.proposedIssues.map((issue) => (
        <li key={issue.id}>
          <strong>{issue.id}</strong>
          <span>{issue.title}</span>
          <small>{issue.severity}</small>
        </li>
      ))}
    </ul>
  </div>
);

export const RunResumeFacts = ({ facts }: RunInputFactsProps) => (
  <div className="run-facts-card run-facts-card--resume">
    <h3>Resume decision</h3>
    {facts.resume.outcome === null ? (
      <p>No resume submitted yet.</p>
    ) : (
      <dl className="run-facts-dl">
        <dt>Outcome</dt><dd>{facts.resume.outcome}</dd>
        {Object.entries(facts.resume.payload).map(([key, value]) => (
          <Fragment key={key}>
            <dt>{key}</dt>
            <dd>{displayPayloadValue(value)}</dd>
          </Fragment>
        ))}
      </dl>
    )}
  </div>
);

type RunOutputFactsProps = {
  readonly facts: DemoRunFacts;
  readonly priority?: RunFactsPriority;
};

export const RunOutputFacts = ({ facts, priority = "summary" }: RunOutputFactsProps) => (
  <div className="run-facts-card" data-output-priority={priority}>
    <h3>Output</h3>
    {facts.output.state === "not-created" ? (
      <p>{facts.output.message}</p>
    ) : (
      <>
        <dl className="run-facts-dl">
          <dt>Created issues</dt>
          <dd>
            <ul className="run-facts-list">
              {facts.output.createdIssues.map((issue) => (
                <li key={issue.id}>
                  <strong>{issue.id}</strong> — {issue.title}
                  <br />
                  <span className="run-facts-url">{issue.url}</span>
                </li>
              ))}
            </ul>
          </dd>
          <dt>Selected issue IDs</dt>
          <dd>{facts.output.output.selected_issue_ids.join(", ")}</dd>
          <dt>Comment</dt>
          <dd>{facts.output.output.comment ?? "none"}</dd>
        </dl>
        <div className="run-facts-scroll-region run-facts-scroll-region--markdown" role="region" aria-label="workflow markdown output">
          <pre className="run-facts-markdown-preview">{facts.output.markdownPreview}</pre>
        </div>
      </>
    )}
  </div>
);

type RunTraceFactsProps = {
  readonly facts: DemoRunFacts;
};

export const RunTraceFacts = ({ facts }: RunTraceFactsProps) => (
  <div className="run-facts-card run-trace-facts">
    <h3>Trace frames</h3>
    {facts.trace.frames.length === 0 ? (
      <p>No trace frames captured.</p>
    ) : (
      <div className="run-facts-scroll-region run-facts-scroll-region--trace" role="region" aria-label="workflow trace frames">
        <ul className="run-facts-list">
          {facts.trace.frames.map((frame) => (
            <li key={frame.nodeId} className="run-trace-frame">
              <strong>{frame.nodeId}</strong>
              <span className="run-trace-step-type">{frame.stepType}</span>
              <span className="run-trace-outcome">{frame.outcome}</span>
              <dl className="run-facts-dl">
                <dt>Resolved input</dt>
                <dd>{frame.resolvedInputLabel}</dd>
                <dt>Output</dt>
                <dd>{frame.outputLabel}</dd>
                <dt>State changes</dt>
                <dd>{frame.stateChangesLabel}</dd>
              </dl>
            </li>
          ))}
        </ul>
      </div>
    )}
  </div>
);
