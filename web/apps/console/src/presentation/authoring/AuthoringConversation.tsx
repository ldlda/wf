import { AssistantOperatorThread } from "../chat/AssistantOperatorThread.js";
import {
  authoringToolGroupId,
  projectPreparedAuthoringThread,
  projectPreparedRunRequestExchange,
  type AuthoringPhaseId,
} from "./authoring-recording.js";
import {
  recordingPhaseForStep,
  type PreparedLifecycleStepId,
} from "./authoring-projection.js";
import type { PreparedLifecycleSubmittedOverrides } from "./prepared-lifecycle-message-state.js";

type AuthoringConversationProps = {
  readonly throughPhase: PreparedLifecycleStepId | AuthoringPhaseId;
  readonly activePhase: PreparedLifecycleStepId | AuthoringPhaseId;
  readonly surface: "stage" | "dock";
  readonly requestOverride?: string | undefined;
  readonly requestOverrides?: PreparedLifecycleSubmittedOverrides | undefined;
  readonly scrollMode?: "active" | "start" | undefined;
  readonly runRequested?: string | null | undefined;
};

/** Renders the same prepared conversation at full-stage or compact-dock scale. */
export const AuthoringConversation = ({
  throughPhase,
  activePhase,
  surface,
  requestOverride,
  requestOverrides,
  scrollMode,
  runRequested,
}: AuthoringConversationProps) => {
  const messages = [
    ...projectPreparedAuthoringThread(
      recordingPhaseForStep(throughPhase),
      requestOverride,
      requestOverrides,
    ),
    ...(runRequested ? projectPreparedRunRequestExchange(runRequested) : []),
  ];

  return (
    <AssistantOperatorThread
      mode={surface === "stage" ? "full" : "dock"}
      surface={surface}
      messages={messages}
      activeToolGroupId={authoringToolGroupId(recordingPhaseForStep(activePhase))}
      scrollMode={runRequested ? "end" : scrollMode}
      ariaLabel="prepared authoring conversation"
    />
  );
};
