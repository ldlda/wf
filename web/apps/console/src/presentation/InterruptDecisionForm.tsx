import { useCallback, useState } from "react";
import type { RunFactsInterrupt } from "./demo-run-facts.js";

type InterruptDecisionFormProps = {
  readonly interrupt: RunFactsInterrupt;
  readonly runId: string;
  readonly onSubmit: (selectedIssueIds: ReadonlyArray<string>, comment: string) => void;
  readonly onCancel: () => void;
  readonly terminalOutcome?: "submitted" | "cancelled" | undefined;
};

export const InterruptDecisionForm = ({
  interrupt,
  runId,
  onSubmit,
  onCancel,
  terminalOutcome,
}: InterruptDecisionFormProps) => {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() =>
    new Set(interrupt.proposedIssues.map((issue) => issue.id)),
  );
  const [comment, setComment] = useState("Create the selected issue.");

  const toggleIssue = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      onSubmit([...selectedIds], comment);
    },
    [selectedIds, comment, onSubmit],
  );

  if (terminalOutcome) {
    return (
      <div className="interrupt-decision-form" role="group" aria-label="operator resume decision">
        <header className="interrupt-decision-form__header">
          <span className="interrupt-decision-form__kind">{interrupt.kind}</span>
          <span className="interrupt-decision-form__run-id">{runId}</span>
        </header>
        <p className="interrupt-decision-form__terminal">
          Outcome: <strong>{terminalOutcome}</strong>
        </p>
      </div>
    );
  }

  return (
    <form
      className="interrupt-decision-form"
      role="group"
      aria-label="operator resume decision"
      onSubmit={handleSubmit}
    >
      <header className="interrupt-decision-form__header">
        <span className="interrupt-decision-form__kind">{interrupt.kind}</span>
        <span className="interrupt-decision-form__run-id">{runId}</span>
      </header>

      <dl className="interrupt-decision-form__meta">
        <dt>Typed</dt>
        <dd>{interrupt.typed ? "yes" : "no"}</dd>
        <dt>Outcomes</dt>
        <dd>{interrupt.outcomes.join(", ")}</dd>
      </dl>

      {interrupt.reportMarkdownPreview && (
        <pre className="interrupt-decision-form__report-preview">
          {interrupt.reportMarkdownPreview}
        </pre>
      )}

      <fieldset className="interrupt-decision-form__issues">
        <legend>Proposed issues</legend>
        {interrupt.proposedIssues.map((issue) => (
          <label key={issue.id} className="interrupt-decision-form__issue-row">
            <input
              type="checkbox"
              checked={selectedIds.has(issue.id)}
              onChange={() => toggleIssue(issue.id)}
            />
            <span className="interrupt-decision-form__issue-title">{issue.title}</span>
            <span className="interrupt-decision-form__issue-severity">{issue.severity}</span>
          </label>
        ))}
      </fieldset>

      <label className="interrupt-decision-form__comment-label">
        Resume comment
        <textarea
          className="interrupt-decision-form__comment"
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          rows={3}
        />
      </label>

      <div className="interrupt-decision-form__actions">
        <button type="submit" className="interrupt-decision-form__submit">
          Submit
        </button>
        <button
          type="button"
          className="interrupt-decision-form__cancel"
          onClick={onCancel}
        >
          Cancel
        </button>
      </div>
    </form>
  );
};
