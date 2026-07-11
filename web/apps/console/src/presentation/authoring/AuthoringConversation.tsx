import { AssistantOperatorThread } from "../chat/AssistantOperatorThread.js";
import {
  authoringToolGroupId,
  projectPreparedAuthoringThread,
  type AuthoringPhaseId,
} from "./authoring-recording.js";

type AuthoringConversationProps = {
  readonly throughPhase: AuthoringPhaseId;
  readonly activePhase: AuthoringPhaseId;
  readonly surface: "stage" | "dock";
  readonly requestOverride?: string | undefined;
  readonly scrollMode?: "active" | "start" | undefined;
  readonly runAction?: { readonly label: string; readonly disabled: boolean; readonly run: () => void } | undefined;
};

/** Renders the same prepared conversation at full-stage or compact-dock scale. */
export const AuthoringConversation = ({
  throughPhase,
  activePhase,
  surface,
  requestOverride,
  scrollMode,
  runAction,
}: AuthoringConversationProps) => (
  <AssistantOperatorThread
    mode={surface === "stage" ? "full" : "dock"}
    surface={surface}
    messages={projectPreparedAuthoringThread(throughPhase, requestOverride)}
    activeToolGroupId={authoringToolGroupId(activePhase)}
    scrollMode={scrollMode}
    ariaLabel="prepared authoring conversation"
    runAction={runAction}
  />
);
