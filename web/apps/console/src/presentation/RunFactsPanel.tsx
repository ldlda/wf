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

type RunOutputFactsProps = {
  readonly facts: DemoRunFacts;
};

export const RunOutputFacts = ({ facts }: RunOutputFactsProps) => (
  <div className="run-facts-card">
    <h3>Output</h3>
    {facts.output.state === "not-created" ? (
      <p>{facts.output.message}</p>
    ) : (
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
        <dt>Markdown preview</dt>
        <dd>
          <pre className="run-facts-markdown-preview">{facts.output.markdownPreview}</pre>
        </dd>
      </dl>
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
    )}
  </div>
);
