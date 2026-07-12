import { useEffect, useState, type FormEvent, type KeyboardEvent } from "react";
import { Button } from "../../components/ui/button.js";
import { Textarea } from "../../components/ui/textarea.js";
import { AuthoringConversation } from "./AuthoringConversation.js";
import type { AuthoringPhaseId } from "./authoring-recording.js";
import type {
  Scene9MessageProjection,
  Scene9SubmittedOverrides,
} from "./scene9-message-state.js";

export type PresentationAssistantPaneProps = {
  readonly phase: AuthoringPhaseId;
  readonly message: Scene9MessageProjection;
  readonly submittedOverrides: Scene9SubmittedOverrides;
  readonly runRequested: string | null;
  readonly onDraftChange: (draft: string) => void;
  readonly onSubmit: (message: string) => void;
};

const phaseLabels: Readonly<Record<AuthoringPhaseId, string>> = {
  discover: "Discover",
  draft: "Draft",
  validate: "Validate",
  artifact: "Artifact",
  deployment: "Deployment",
};

/**
 * Stable Scene 9 boundary for the prepared assistant surface.
 *
 * The pane owns only the transient composer buffer. Submitted text is handed
 * back to the Scene 9 controller so the replay can project it later.
 */
export const PresentationAssistantPane = ({
  phase,
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
  const submit = (event?: FormEvent<HTMLFormElement>) => {
    event?.preventDefault();
    if (canSubmit) onSubmit(draft);
  };
  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  };

  return (
    <aside
      className="presentation-assistant-pane"
      aria-label="prepared authoring assistant"
      data-phase={phase}
      data-surface="prepared-replay"
    >
      <header className="presentation-assistant-pane__header">
        <p className="presentation-assistant-pane__eyebrow">Prepared workflow</p>
        <h2>Authoring assistant</h2>
        <p>Current phase: {phaseLabels[phase]}</p>
        <p className="presentation-assistant-pane__disclosure">
          Prepared replay only. No live actions or RPC calls.
        </p>
      </header>
      <div className="presentation-assistant-pane__conversation">
        <AuthoringConversation
          throughPhase={phase}
          activePhase={phase}
          surface="stage"
          scrollMode="start"
          requestOverrides={submittedOverrides}
        />
      </div>
      <form className="presentation-assistant-pane__composer" onSubmit={submit}>
        <label htmlFor="scene9-authoring-message">Message to authoring assistant</label>
        <Textarea
          id="scene9-authoring-message"
          value={draft}
          placeholder={message.placeholder}
          disabled={runRequested !== null}
          onChange={(event) => updateDraft(event.target.value)}
          onKeyDown={handleKeyDown}
          aria-describedby="scene9-authoring-message-help"
        />
        <div className="presentation-assistant-pane__composer-actions">
          <Button type="submit" disabled={!canSubmit}>
            Send message
          </Button>
        </div>
        <p id="scene9-authoring-message-help" className="presentation-assistant-pane__composer-help">
          Shift+Enter adds a new line. This is a deterministic prepared replay, not a live model request.
        </p>
        {runRequested !== null ? (
          <p role="status" className="presentation-assistant-pane__run-status">
            Run request prepared for the next execution slice.
          </p>
        ) : null}
      </form>
    </aside>
  );
};
