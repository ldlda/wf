import { useReducer } from "react";
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

export const AgentHandoffScene = ({ beat }: AgentHandoffSceneProps) => {
  const [entryState, dispatch] = useReducer(scene8EntryReducer, initialScene8EntryState);

  return (
    <section
      className="agent-handoff-scene"
      aria-label="prepared agent request"
      data-handoff-phase="discover"
      data-presentation-surface="editorial"
    >
      {beat.id === "request" && <Scene8ChatEntry state={entryState} dispatch={dispatch} />}
    </section>
  );
};
