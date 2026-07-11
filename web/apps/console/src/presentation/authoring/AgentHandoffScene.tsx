import { AuthoringConversation } from "./AuthoringConversation.js";
import type { AuthoringPhaseId } from "./authoring-recording.js";
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
  const phase: AuthoringPhaseId = beat.id === "handoff" ? "deployment" : "discover";
  const phases: readonly { readonly id: AuthoringPhaseId; readonly label: string }[] = [
    { id: "discover", label: "Discover" },
    { id: "draft", label: "Draft" },
    { id: "validate", label: "Validate" },
    { id: "artifact", label: "Artifact" },
    { id: "deployment", label: "Deployment" },
  ];
  const activeIndex = phases.findIndex(({ id }) => id === phase);

  return (
    <section className="agent-handoff-scene" aria-label="prepared agent handoff" data-handoff-phase={phase}>
      <header className="agent-handoff-scene__header">
        <span>Prepared replay</span>
        <strong>External agent → workflow substrate</strong>
        <p>One conversation, with public operations and interpreted results.</p>
      </header>
      <ol className="agent-handoff-scene__rail" aria-label="prepared handoff phases">
        {phases.map((item, index) => (
          <li key={item.id} data-active={index === activeIndex ? "true" : "false"}>
            <span>{index + 1}</span>
            <strong>{item.label}</strong>
          </li>
        ))}
      </ol>
      <div className="agent-handoff-scene__thread">
        <AuthoringConversation
          throughPhase={phase}
          activePhase={phase}
          surface="stage"
        />
      </div>
    </section>
  );
};
