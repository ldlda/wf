import { AuthoringConversation } from "./AuthoringConversation.js";
import type { SceneBeatDefinition, SceneDefinition } from "../storyboard.js";

type AgentHandoffSceneProps = {
  readonly scene: SceneDefinition;
  readonly beat: SceneBeatDefinition;
};

/**
 * Full-screen prepared-authoring conversation for Scene 8.
 *
 * The request beat shows the operator asking the agent to prepare a report;
 * the handoff beat reveals the full completed conversation with all phases.
 * Neither run actions nor approval actions are passed because this is a
 * prepared recording, not a live agent interaction.
 */
export const AgentHandoffScene = ({ beat }: AgentHandoffSceneProps) => {
  const phase = beat.id === "handoff" ? "deployment" : "discover";

  return (
    <AuthoringConversation
      throughPhase={phase}
      activePhase={phase}
      surface="stage"
    />
  );
};
