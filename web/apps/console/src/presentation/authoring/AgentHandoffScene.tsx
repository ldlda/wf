import { useMemo } from "react";
import { agentTextMessage } from "../../demo/agent/events.js";
import { AssistantOperatorThread } from "../chat/AssistantOperatorThread.js";
import { projectPreparedAuthoring } from "./authoring-recording.js";
import type { SceneBeatDefinition, SceneDefinition } from "../storyboard.js";

type AgentHandoffSceneProps = {
  readonly scene: SceneDefinition;
  readonly beat: SceneBeatDefinition;
};

const requestMessages = [
  agentTextMessage("handoff-user-1", "user", "We need to prepare a report workflow for the lda_report scenario. Use the available CLI tools to inspect, author, and deploy it."),
  agentTextMessage("handoff-assistant-1", "assistant", "Let me inspect the available sources, capabilities, and schemas first."),
];

/**
 * Full-screen prepared-authoring conversation for Scene 8.
 *
 * The request beat shows the operator asking the agent to prepare a report;
 * the handoff beat reveals the full completed conversation with all phases.
 * Neither run actions nor approval actions are passed because this is a
 * prepared recording, not a live agent interaction.
 */
export const AgentHandoffScene = ({ beat }: AgentHandoffSceneProps) => {
  const messages = useMemo(() => {
    if (beat.id === "handoff") {
      const recording = projectPreparedAuthoring();
      const result: ReturnType<typeof agentTextMessage>[] = [];
      let index = 0;
      for (const phase of recording) {
        for (const turn of phase.conversation) {
          result.push(
            agentTextMessage(`msg-${index++}`, turn.role, turn.text),
          );
        }
      }
      return result;
    }
    return requestMessages;
  }, [beat.id]);

  return (
    <AssistantOperatorThread
      mode="full"
      messages={messages}
      ariaLabel="prepared authoring conversation"
    />
  );
};
