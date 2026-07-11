import { AuthoringConversation } from "./AuthoringConversation.js";
import type { AuthoringPhaseId } from "./authoring-recording.js";

type PresentationAssistantPaneProps = {
  readonly phase: AuthoringPhaseId;
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
 * The pane deliberately passes no action handlers: its conversation is a
 * replay projection, not a live assistant runtime or authoring client.
 */
export const PresentationAssistantPane = ({ phase }: PresentationAssistantPaneProps) => (
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
        surface="dock"
      />
    </div>
  </aside>
);
