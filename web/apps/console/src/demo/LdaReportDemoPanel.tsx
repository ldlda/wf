import { useEffect, useMemo, useState } from "react";
import { ldaReportSetupCommands } from "./ldaReportDemoConfig.js";
import { DemoTimelineControls } from "./DemoTimelineControls.js";
import { DemoTimeline } from "./DemoTimeline.js";
import type { DemoTimelineController } from "./useDemoTimeline.js";

const DEFAULT_REVIEW_COMMENT = "Create selected issues before the defense.";

export const LdaReportDemoPanel = ({ controller }: { readonly controller: DemoTimelineController }) => {
  const { state } = controller;
  const [selectedIds, setSelectedIds] = useState<ReadonlySet<string>>(new Set());
  const [comment, setComment] = useState(DEFAULT_REVIEW_COMMENT);

  const proposedIssues = controller.interruptPayload?.proposed_issues ?? [];
  const selectedIssueIds = useMemo(() => [...selectedIds], [selectedIds]);

  useEffect(() => {
    setSelectedIds(new Set());
    setComment(DEFAULT_REVIEW_COMMENT);
  }, [state.mode, state.phase, controller.interruptPayload]);

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
      </div>

      {state.mode === "live" && controller.missingDeploymentMessage && (
        <div className="demo-panel__missing" role="status">
          <h3>Prepared demo deployment is missing</h3>
          <p>Run the example RPC server/store setup outside the UI, then refresh.</p>
          <pre><code>{ldaReportSetupCommands.join("\n")}</code></pre>
        </div>
      )}

      <DemoTimelineControls
        state={state}
        inFlight={controller.inFlight}
        canStart={controller.canStart}
        setMode={controller.setMode}
        start={controller.start}
        pause={controller.pause}
        play={controller.play}
        next={controller.next}
        restart={controller.restart}
      />

      {state.mode === "replay" && (
        <p className="demo-replay-label" role="status">
          Recorded replay &middot; {controller.recordingId}
        </p>
      )}

      <DemoTimeline state={state} />

      {(state.phase === "running" || state.phase === "paused") && (
        <p role="status">Demo workflow is {state.phase}.</p>
      )}

      {state.phase === "review" && controller.interruptPayload && (
        <div className="demo-panel__review">
          <h3>Typed interrupt: issue_review</h3>
          <div className="demo-panel__markdown">
            <h4>Generated report preview</h4>
            <pre><code>{controller.interruptPayload.report_markdown}</code></pre>
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
                  <small>{issue.id} &middot; {issue.severity}</small>
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
            {state.mode === "replay" ? (
              <button
                onClick={() => void controller.submitSelectedIssues(selectedIssueIds, comment)}
                disabled={selectedIssueIds.length === 0}
              >
                Continue
              </button>
            ) : (
              <button
                onClick={() => void controller.submitSelectedIssues(selectedIssueIds, comment)}
                disabled={selectedIssueIds.length === 0}
              >
                Resume and create selected issues
              </button>
            )}
            <button onClick={() => void controller.requestRevision(comment)}>
              Request revision
            </button>
          </div>
          {state.mode === "replay" && (
            <p className="demo-replay-note" role="note">
              Replay does not create real issues.
            </p>
          )}
        </div>
      )}

      {state.phase === "completed" && controller.output && (
        <div className="demo-panel__complete">
          <h3>Completed: {controller.output.approved ? "issues created" : "revision requested"}</h3>
          <p>Created issues: {controller.output.created_issues.length}</p>
          <ul>
            {controller.output.created_issues.map((issue) => (
              <li key={issue.id}>
                <strong>{issue.id}</strong> {issue.title}
              </li>
            ))}
          </ul>
          <h4>Final markdown</h4>
          <pre><code>{controller.output.markdown}</code></pre>
          <h4>Execution trace ({controller.trace?.frames.length ?? 0} frames)</h4>
          {controller.trace && controller.trace.frames.length > 0 ? (
            <table>
              <thead>
                <tr>
                  <th>Node</th>
                  <th>Step</th>
                  <th>Outcome</th>
                </tr>
              </thead>
              <tbody>
                {controller.trace.frames.map((frame, i) => (
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

      {state.phase === "failed" && state.error && (
        <p role="alert">{state.error}</p>
      )}
    </section>
  );
};
