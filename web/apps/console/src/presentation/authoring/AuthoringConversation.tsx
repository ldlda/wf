import { AssistantOperatorThread } from "../chat/AssistantOperatorThread.js";
import {
  authoringToolGroupId,
  projectPreparedAuthoringThread,
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
};

/** Renders the same prepared conversation at full-stage or compact-dock scale. */
export const AuthoringConversation = ({
  throughPhase,
  activePhase,
  surface,
  requestOverride,
  requestOverrides,
  scrollMode,
}: AuthoringConversationProps) => (
  <AssistantOperatorThread
    mode={surface === "stage" ? "full" : "dock"}
    surface={surface}
    messages={projectPreparedAuthoringThread(
      recordingPhaseForStep(throughPhase),
      requestOverride,
      requestOverrides,
    )}
    activeToolGroupId={authoringToolGroupId(recordingPhaseForStep(activePhase))}
    scrollMode={scrollMode}
    ariaLabel="prepared authoring conversation"
  />
);
