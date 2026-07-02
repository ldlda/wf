import { useMemo, useState } from "react";
import { ldaReportSetupCommands } from "./ldaReportDemoConfig.js";
import type { useLdaReportDemo } from "./useLdaReportDemo.js";

type Controller = ReturnType<typeof useLdaReportDemo>;

export const LdaReportDemoPanel = ({ controller }: { readonly controller: Controller }) => {
  const { state } = controller;
  const [selectedIds, setSelectedIds] = useState<ReadonlySet<string>>(new Set());
  const [comment, setComment] = useState("Create selected issues before the defense.");

  const proposedIssues = state.interruptPayload?.proposed_issues ?? [];
  const selectedIssueIds = useMemo(() => [...selectedIds], [selectedIds]);
  const runInProgress =
    state.phase === "starting" ||
    state.phase === "interrupted" ||
    state.phase === "resuming";

  return (
    <section aria-label="lda report workflow demo" className="demo-panel">
      <div className="demo-panel__header">
        <div>
          <h2>lda report workflow demo</h2>
          <p>
            Prepared workflow: start run, stop at typed issue review,
            resume, then inspect trace and generated issues.
          </p>
        </div>
        <button onClick={controller.refresh} disabled={runInProgress}>
          Refresh demo state
        </button>
      </div>

      {state.phase === "missing" && (
        <div className="demo-panel__missing" role="status">
          <h3>Prepared demo deployment is missing</h3>
          <p>Run the example RPC server/store setup outside the UI, then refresh.</p>
          <pre><code>{ldaReportSetupCommands.join("\n")}</code></pre>
        </div>
      )}

      {(state.phase === "ready" || state.phase === "checking") && (
        <button
          onClick={controller.startRun}
          disabled={state.phase === "checking"}
        >
          Start demo run
        </button>
      )}

      {(state.phase === "starting" || state.phase === "resuming") && (
        <p role="status">Demo workflow is {state.phase}.</p>
      )}

      {state.phase === "interrupted" && state.interruptPayload && (
        <div className="demo-panel__review">
          <h3>Typed interrupt: issue_review</h3>
          <p>Run id: <code>{state.runId}</code></p>
          <div className="demo-panel__markdown">
            <h4>Generated report preview</h4>
            <pre><code>{state.interruptPayload.report_markdown}</code></pre>
          </div>
          <fieldset>
            <legend>Select issues to create</legend>
            {proposedIssues.map((issue) => (
              <label key={issue.id} className="demo-panel__issue">
                <input
                  type="checkbox"
                  checked={selectedIds.has(issue.id)}
                  onChange={(event) => {
                    const next = new Set(selectedIds);
                    if (event.currentTarget.checked) {
                      next.add(issue.id);
                    } else {
                      next.delete(issue.id);
                    }
                    setSelectedIds(next);
                  }}
                />
                <span>
                  <strong>{issue.title}</strong>
                  <small>{issue.id} · {issue.severity}</small>
                  <span>{issue.body}</span>
                </span>
              </label>
            ))}
          </fieldset>
          <label>
            Review comment
            <textarea value={comment} onChange={(event) => setComment(event.currentTarget.value)} />
          </label>
          <div className="demo-panel__actions">
            <button
              onClick={() => controller.submitSelectedIssues(selectedIssueIds, comment)}
              disabled={selectedIssueIds.length === 0}
            >
              Resume and create selected issues
            </button>
            <button onClick={() => controller.cancelReview(comment)}>
              Cancel review
            </button>
          </div>
        </div>
      )}

      {state.phase === "completed" && state.output && (
        <div className="demo-panel__complete">
          <h3>Completed: {state.output.approved ? "issues created" : "revision requested"}</h3>
          <p>Created issues: {state.output.created_issues.length}</p>
          <ul>
            {state.output.created_issues.map((issue) => (
              <li key={issue.id}>
                <strong>{issue.id}</strong> {issue.title}
              </li>
            ))}
          </ul>
          <h4>Final markdown</h4>
          <pre><code>{state.output.markdown}</code></pre>
          <h4>Execution trace ({state.trace?.frames.length ?? 0} frames)</h4>
          {state.trace && state.trace.frames.length > 0 ? (
            <table>
              <thead>
                <tr>
                  <th>Node</th>
                  <th>Step</th>
                  <th>Outcome</th>
                </tr>
              </thead>
              <tbody>
                {state.trace.frames.map((frame, i) => (
                  <tr key={i}>
                    <td><code>{frame.nodeId}</code></td>
                    <td>{frame.stepType}</td>
                    <td>{frame.outcome}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p>No trace frames available.</p>
          )}
        </div>
      )}

      {state.phase === "error" && state.message && (
        <p role="alert">{state.message}</p>
      )}
    </section>
  );
};
