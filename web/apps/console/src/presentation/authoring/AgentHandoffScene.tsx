import { useReducer } from "react";
import { AuthoringConversation } from "./AuthoringConversation.js";
import { Scene8ChatEntry } from "./Scene8ChatEntry.js";
import {
  initialScene8EntryState,
  scene8EntryReducer,
} from "./scene8-entry-state.js";
import type { SceneBeatDefinition, SceneDefinition } from "../storyboard.js";

type AgentHandoffSceneProps = {
  readonly scene: SceneDefinition;
  readonly beat: SceneBeatDefinition;
};

/**
 * Scene 8 request and handoff beats share one local deterministic entry state.
 */
export const AgentHandoffScene = ({ beat }: AgentHandoffSceneProps) => {
  const [entryState, dispatch] = useReducer(scene8EntryReducer, initialScene8EntryState);
  const phase = beat.id === "handoff" ? "deployment" : "discover";

  return (
    <section
      className="agent-handoff-scene"
      aria-label="prepared agent handoff"
      data-handoff-phase={phase}
      data-presentation-surface="editorial"
    >
      {beat.id === "request" ? (
        <Scene8ChatEntry state={entryState} dispatch={dispatch} />
      ) : (
        <div className="agent-handoff-scene__handoff">
          <AuthoringConversation
            throughPhase="deployment"
            activePhase="deployment"
            surface="stage"
            {...(entryState.phase === "submitted" ? { requestOverride: entryState.request } : {})}
          />
        </div>
      )}
    </section>
  );
};
