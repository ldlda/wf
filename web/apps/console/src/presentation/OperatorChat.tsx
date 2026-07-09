import { PREPARE_THESIS_REPORT_RECIPE } from "../demo/agent/recipes.js";
import type { AgentMessage } from "../demo/agent/events.js";
import type { TimelineAgentController } from "../demo/agent/timelineAgent.js";
import type { PresentationState } from "./presentation-state.js";
import { compositionForState } from "./presentation-state.js";
import { SchemaApprovalSurface } from "./approval/SchemaApprovalSurface.js";
import {
  Conversation,
  ConversationContent,
  Message,
  MessageContent,
  MessageResponse,
  PromptAction,
  Tool,
  ToolInput,
  ToolOutput,
} from "./chat/ChatPrimitives.js";
import { projectAgentMessage, type ProjectedChatPart } from "./chat/agentChatProjection.js";

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

const renderProjectedPart = (
  part: ProjectedChatPart,
  key: string,
  submit?: () => void,
  cancel?: () => void,
) => {
  switch (part.kind) {
    case "text":
      return <MessageResponse key={key}>{part.text}</MessageResponse>;
    case "tool":
      return (
        <Tool key={key} label={part.label} name={part.name} state={part.state} defaultOpen={part.defaultOpen}>
          {"input" in part ? <ToolInput input={part.input} /> : null}
          {"output" in part ? <ToolOutput status={part.state} output={part.output} /> : null}
        </Tool>
      );
    case "approval":
      return (
        <Tool key={key} label="Approval required" name={part.name} state="pending" defaultOpen>
          <MessageResponse>{part.prompt}</MessageResponse>
          {part.contract ? (
            <SchemaApprovalSurface
              title={`${part.contract.kind.replaceAll("_", " ")} resume`}
              schema={part.contract.resumeSchema}
              payload={part.contract.resumePayloadPreview}
              outcomes={part.contract.outcomes}
              runId={part.contract.runId}
              onSubmit={submit}
              onCancel={cancel}
            />
          ) : (
            <div className="chat-approval-actions">
              <button type="button" onClick={submit} disabled={!submit}>Approve</button>
              <button type="button" onClick={cancel} disabled={!cancel}>Deny</button>
            </div>
          )}
        </Tool>
      );
    case "error":
      return <MessageResponse key={key}>{part.message}</MessageResponse>;
  }
};

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
      {timelineAgent ? (
        <PromptAction
          label={timelineAgent.runLabel}
          disabled={!timelineAgent.canRun}
          onClick={() => void timelineAgent.runPreparedWorkflow()}
        />
      ) : null}
      <Conversation mode={composition.chatMode}>
        <ConversationContent>
          {visibleMessages.map(projectAgentMessage).map((message) => (
            <Message key={message.id} from={message.from}>
              <MessageContent>
                {message.parts.map((part, index) => renderProjectedPart(part, `${message.id}-${index}`, submit, cancel))}
              </MessageContent>
            </Message>
          ))}
        </ConversationContent>
      </Conversation>
    </aside>
  );
};
