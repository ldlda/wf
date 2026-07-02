import type { PresentationState } from "./presentation-state.js";

type OperatorChatProps = {
  readonly state: PresentationState;
};

export const OperatorChat = ({ state }: OperatorChatProps) => (
  <aside className="operator-chat" data-mode={state.chatMode} aria-label="scripted operator chat">
    <div className="chat-message chat-message--operator">
      <strong>Operator</strong>
      <p>Prepare the thesis readiness report.</p>
    </div>
    <div className="chat-message chat-message--system">
      <strong>lda.chat</strong>
      <p>Found prepared workflow recipe: <code>lda_report_case_study</code>.</p>
    </div>
    <div className="chat-message chat-message--system">
      <strong>lda.chat</strong>
      <p>Replay mode is active. Live execution is available when connected.</p>
    </div>
  </aside>
);
