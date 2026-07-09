import { PREPARE_THESIS_REPORT_RECIPE } from "../demo/agent/recipes.js";
import type { AgentMessage } from "../demo/agent/events.js";
import type { TimelineAgentController } from "../demo/agent/timelineAgent.js";
import type { PresentationState } from "./presentation-state.js";
import { compositionForState } from "./presentation-state.js";
import { AssistantOperatorThread } from "./chat/AssistantOperatorThread.js";

type OperatorChatProps = {
  readonly state: PresentationState;
  readonly messages?: ReadonlyArray<AgentMessage> | undefined;
  readonly timelineAgent?: TimelineAgentController | undefined;
  readonly onApprove?: (() => void) | undefined;
  readonly onDeny?: (() => void) | undefined;
};

const fallbackMessages = (state: PresentationState): ReadonlyArray<AgentMessage> => [
  { id: "fallback-user", role: "user", parts: [{ type: "text", text: PREPARE_THESIS_REPORT_RECIPE.userPrompt }] },
  {
    id: "fallback-system",
    role: "assistant",
    parts: [
      { type: "text", text: `Found prepared workflow recipe: ${PREPARE_THESIS_REPORT_RECIPE.id}.` },
      {
        type: "text",
        text: state.playbackMode === "replay"
          ? "Replay mode is active. Live execution is available when connected."
          : "Live execution is active. Operations are being sent to the connected workflow server.",
      },
    ],
  },
];

export const OperatorChat = ({ state, messages, timelineAgent, onApprove, onDeny }: OperatorChatProps) => {
  const visibleMessages = messages && messages.length > 0
    ? messages
    : timelineAgent && timelineAgent.messages.length > 0
      ? timelineAgent.messages
      : fallbackMessages(state);
  const submit = timelineAgent?.submitSelectedIssues ?? onApprove;
  const cancel = timelineAgent?.cancelReview ?? onDeny;
  const composition = compositionForState(state);
  const presentationSurface = composition.chatTheme === "light" ? "editorial" : "night";
  return (
    <aside
      className="operator-chat"
      data-mode={composition.chatMode}
      data-chat-theme={composition.chatTheme}
      data-presentation-surface={presentationSurface}
      aria-label="scripted operator chat"
    >
      <AssistantOperatorThread
        mode={composition.chatMode}
        messages={visibleMessages}
        runAction={timelineAgent ? {
          label: timelineAgent.runLabel,
          disabled: !timelineAgent.canRun,
          run: () => void timelineAgent.runPreparedWorkflow(),
        } : undefined}
        submitApproval={submit}
        cancelApproval={cancel}
      />
    </aside>
  );
};
