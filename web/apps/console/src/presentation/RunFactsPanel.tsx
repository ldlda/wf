import { Fragment } from "react";
import { factValueKind, type DemoRunFacts } from "./demo-run-facts.js";

type RunInputFactsProps = {
  readonly facts: DemoRunFacts;
  readonly density?: "normal" | "compact";
};

type InterruptPayloadFactsProps = RunInputFactsProps & {
  readonly priority?: "normal" | "primary";
};

export const RunInputFacts = ({ facts, density = "normal" }: RunInputFactsProps) => (
  <div className="run-facts-card" role="region" aria-label="workflow input summary" data-density={density}>
    <h3>Workflow input</h3>
    <dl className="run-facts-dl">
      <dt>Selected documents</dt>
      <dd>
        <ul className="run-facts-list" aria-label="selected documents">
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

export const InterruptPayloadFacts = ({ facts, priority = "normal" }: InterruptPayloadFactsProps) => (
  <div
    className="run-facts-card run-facts-card--interrupt"
    role="region"
    aria-label="interrupt report and proposed issues"
    data-priority={priority}
  >
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
  <div
    className="run-facts-card"
    role="region"
    aria-label={priority === "report" ? "workflow output report" : "workflow output summary"}
    data-output-priority={priority}
  >
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
                  <strong>{issue.id}</strong>
                  {priority === "report" ? <> — {issue.title}</> : null}
                  {priority === "report" ? (
                    <>
                      <br />
                      <span className="run-facts-url">{issue.url}</span>
                    </>
                  ) : null}
                </li>
              ))}
            </ul>
          </dd>
          <dt>Selected issue IDs</dt>
          <dd>{facts.output.output.selected_issue_ids.join(", ")}</dd>
        </dl>
        {priority === "report" ? (
          <div className="run-facts-scroll-region run-facts-scroll-region--markdown" role="region" aria-label="workflow markdown output">
            <pre className="run-facts-markdown-preview">{facts.output.markdownPreview}</pre>
          </div>
        ) : null}
      </>
    )}
  </div>
);

type RunTraceFactsProps = {
  readonly facts: DemoRunFacts;
};

const TraceFact = ({ label, value }: { readonly label: string; readonly value: string }) => (
  <div className="run-trace-frame__fact" data-value-kind={factValueKind(value)}>
    <dt>{label}</dt>
    <dd><code>{value}</code></dd>
  </div>
);

export const RunTraceFacts = ({ facts }: RunTraceFactsProps) => (
  <div className="run-facts-card run-trace-facts" role="region" aria-label="workflow trace proof">
    <h3>Recorded execution trace</h3>
    {facts.trace.frames.length === 0 ? (
      <p>No trace entries recorded for this view.</p>
    ) : (
      <div className="run-facts-scroll-region run-facts-scroll-region--trace" role="region" aria-label="workflow trace frames">
        <ul className="run-facts-list">
          {facts.trace.frames.map((frame, index) => (
            <li key={`${frame.nodeId}-${index}`} className="run-trace-frame" data-trace-node={frame.nodeId}>
              <header className="run-trace-frame__header">
                <strong>{frame.nodeId}</strong>
                <span className="run-trace-step-type">{frame.stepType}</span>
                <span className="run-trace-outcome">{frame.outcome}</span>
              </header>
              <dl className="run-trace-frame__facts">
                <TraceFact label="Resolved input" value={frame.resolvedInputLabel} />
                <TraceFact label="Output" value={frame.outputLabel} />
                <TraceFact label="State changes" value={frame.stateChangesLabel} />
              </dl>
            </li>
          ))}
        </ul>
      </div>
    )}
  </div>
);
