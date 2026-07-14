import { useEffect, useState } from "react";
import { Button } from "../../components/ui/button.js";
import { Textarea } from "../../components/ui/textarea.js";
import { AuthoringConversation } from "./AuthoringConversation.js";
import type { AuthoringPhaseId } from "./authoring-recording.js";
import type {
  PreparedLifecycleMessageProjection,
  PreparedLifecycleSubmittedOverrides,
} from "./prepared-lifecycle-message-state.js";
import type { PreparedLifecycleStepId } from "./authoring-projection.js";
import { PREPARED_COMPOSER_HELP, usePreparedComposerSubmit } from "./usePreparedComposerSubmit.js";

export type PresentationAssistantPaneProps = {
  readonly phase: PreparedLifecycleStepId | AuthoringPhaseId;
  readonly visualRole?: "support";
  readonly message: PreparedLifecycleMessageProjection;
  readonly submittedOverrides: PreparedLifecycleSubmittedOverrides;
  readonly runRequested: string | null;
  readonly onDraftChange: (draft: string) => void;
  readonly onSubmit: (message: string) => void;
};

const phaseLabels: Readonly<Record<PreparedLifecycleStepId | AuthoringPhaseId, string>> = {
  discover: "Discover",
  draft: "Draft",
  diagnose: "Diagnose",
  repair: "Repair",
  validate: "Validate",
  artifact: "Artifact",
  deployment: "Deployment",
};

/**
 * Stable prepared lifecycle boundary for the prepared assistant surface.
 *
 * The pane owns only the transient composer buffer. Submitted text is handed
 * back to the lifecycle controller so the replay can project it later.
 */
export const PresentationAssistantPane = ({
  phase,
  visualRole,
  message,
  submittedOverrides,
  runRequested,
  onDraftChange,
  onSubmit,
}: PresentationAssistantPaneProps) => {
  const [draft, setDraft] = useState(message.prefill);

  useEffect(() => {
    setDraft(message.prefill);
  }, [phase, message.prefill]);

  const canSubmit = draft.trim().length > 0 && runRequested === null;
  const updateDraft = (nextDraft: string) => {
    setDraft(nextDraft);
    onDraftChange(nextDraft);
  };
  const { submit, handleKeyDown } = usePreparedComposerSubmit(
    canSubmit,
    () => {
      onSubmit(draft);
      setDraft("");
    },
  );

  return (
    <aside
      className="presentation-assistant-pane"
      aria-label="prepared authoring assistant"
      data-phase={phase}
      data-surface="prepared-replay"
      data-visual-role={visualRole}
    >
      <header className="presentation-assistant-pane__header">
        <p className="presentation-assistant-pane__eyebrow">Prepared workflow</p>
        <h2>Authoring assistant</h2>
        <p>Current phase: {phaseLabels[phase]}</p>
        <p className="presentation-assistant-pane__disclosure">
          Prepared assistant transcript. The final run request uses the configured demo target.
        </p>
      </header>
      <div className="presentation-assistant-pane__conversation">
        <AuthoringConversation
          throughPhase={phase}
          activePhase={phase}
          surface="stage"
          requestOverrides={submittedOverrides}
          runRequested={runRequested}
        />
      </div>
      <form className="presentation-assistant-pane__composer" onSubmit={submit}>
        <label htmlFor="prepared-lifecycle-authoring-message">Message to authoring assistant</label>
        <Textarea
          id="prepared-lifecycle-authoring-message"
          value={draft}
          placeholder={message.placeholder}
          disabled={runRequested !== null}
          onChange={(event) => updateDraft(event.target.value)}
          onKeyDown={handleKeyDown}
          aria-describedby="prepared-lifecycle-authoring-message-help"
        />
        <div className="presentation-assistant-pane__composer-actions">
          <Button type="submit" disabled={!canSubmit}>
            Send message
          </Button>
        </div>
        <p id="prepared-lifecycle-authoring-message-help" className="presentation-assistant-pane__composer-help">
          {PREPARED_COMPOSER_HELP}
        </p>
        {runRequested !== null ? (
          <p role="status" className="presentation-assistant-pane__run-status">
            Prepared run receipt added. Continue when you are ready.
          </p>
        ) : null}
      </form>
    </aside>
  );
};
