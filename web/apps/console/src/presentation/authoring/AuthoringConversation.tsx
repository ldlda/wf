import { AssistantOperatorThread } from "../chat/AssistantOperatorThread.js";
import {
  authoringToolGroupId,
  projectPreparedAuthoringThread,
  type AuthoringPhaseId,
} from "./authoring-recording.js";
import type { Scene9SubmittedOverrides } from "./scene9-message-state.js";

type AuthoringConversationProps = {
  readonly throughPhase: AuthoringPhaseId;
  readonly activePhase: AuthoringPhaseId;
  readonly surface: "stage" | "dock";
  readonly requestOverride?: string | undefined;
  readonly requestOverrides?: Scene9SubmittedOverrides | undefined;
  readonly scrollMode?: "active" | "start" | undefined;
  readonly runAction?: { readonly label: string; readonly disabled: boolean; readonly run: () => void } | undefined;
};

/** Renders the same prepared conversation at full-stage or compact-dock scale. */
export const AuthoringConversation = ({
  throughPhase,
  activePhase,
  surface,
  requestOverride,
  requestOverrides,
  scrollMode,
  runAction,
}: AuthoringConversationProps) => (
  <AssistantOperatorThread
    mode={surface === "stage" ? "full" : "dock"}
    surface={surface}
    messages={projectPreparedAuthoringThread(throughPhase, requestOverride, requestOverrides)}
    activeToolGroupId={authoringToolGroupId(activePhase)}
    scrollMode={scrollMode}
    ariaLabel="prepared authoring conversation"
    runAction={runAction}
  />
);
