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
};

/** Renders the same prepared conversation at full-stage or compact-dock scale. */
export const AuthoringConversation = ({
  throughPhase,
  activePhase,
  surface,
}: AuthoringConversationProps) => (
  <AssistantOperatorThread
    mode={surface === "stage" ? "full" : "dock"}
    surface={surface}
    messages={projectPreparedAuthoringThread(throughPhase)}
    activeToolGroupId={authoringToolGroupId(activePhase)}
    ariaLabel="prepared authoring conversation"
  />
);
