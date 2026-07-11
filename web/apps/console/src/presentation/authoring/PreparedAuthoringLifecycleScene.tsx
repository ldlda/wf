import { projectPreparedAuthoringPhase } from "./authoring-projection.js";
import { AuthoringConversation } from "./AuthoringConversation.js";
import { AuthoringPhaseVisual } from "./AuthoringPhaseVisual.js";
import type { AuthoringPhaseId } from "./authoring-recording.js";
import type { SceneBeatDefinition, SceneDefinition } from "../storyboard.js";
import { StageCaption } from "../StageCaption.js";

type PreparedAuthoringLifecycleSceneProps = {
  readonly scene: SceneDefinition;
  readonly beat: SceneBeatDefinition;
};

const phases: readonly { readonly id: AuthoringPhaseId; readonly label: string }[] = [
  { id: "discover", label: "Discover" },
  { id: "draft", label: "Draft" },
  { id: "validate", label: "Validate" },
  { id: "artifact", label: "Artifact" },
  { id: "deployment", label: "Deployment" },
];

/**
 * Scene 9 — Prepared workflow authoring lifecycle.
 *
 * Each beat shows a compact orientation rail and one dominant phase projection
 * sourced from the prepared authoring recording. The same Scene 8 conversation
 * remains below the canvas as a beat-synchronized assistant dock.
 */
export const PreparedAuthoringLifecycleScene = ({ scene, beat }: PreparedAuthoringLifecycleSceneProps) => {
  const beatId = beat.id as AuthoringPhaseId;
  const projection = projectPreparedAuthoringPhase(beatId);

  return (
    <>
      <StageCaption eyebrow="Prepared workflow" title={scene.title}>
        <p>{beat.caption}</p>
      </StageCaption>
      <section
        className="prepared-lifecycle-scene"
        aria-label="prepared workflow authoring lifecycle"
        data-active-phase={beatId}
      >
        <ol className="prepared-lifecycle-scene__rail" aria-label="authoring phase rail">
          {phases.map((phase) => (
            <li key={phase.id} data-active={phase.id === beatId ? "true" : "false"}>
              <strong>{phase.label}</strong>
            </li>
          ))}
        </ol>

        <article className="prepared-lifecycle-scene__projection" key={beatId}>
          <AuthoringPhaseVisual projection={projection} />
        </article>
        <div className="prepared-lifecycle-scene__dock">
          <AuthoringConversation
            throughPhase={beatId}
            activePhase={beatId}
            surface="dock"
          />
        </div>
      </section>
    </>
  );
};
