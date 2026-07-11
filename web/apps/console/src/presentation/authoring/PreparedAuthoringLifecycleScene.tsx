import { projectPreparedAuthoringPhase } from "./authoring-projection.js";
import { AuthoringPhaseVisual } from "./AuthoringPhaseVisual.js";
import { PresentationAssistantPane } from "./PresentationAssistantPane.js";
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
 * Each beat shows a persistent prepared assistant beside one dominant phase
 * projection sourced from the prepared authoring recording.
 */
export const PreparedAuthoringLifecycleScene = ({ scene, beat }: PreparedAuthoringLifecycleSceneProps) => {
  // Storyboard beats normally match these IDs. Discovery is a safe projection
  // if a future beat reaches this scene before its authoring mapping is added.
  const beatId = phases.find((phase) => phase.id === beat.id)?.id ?? "discover";
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
        data-primary-surface="authoring-phase"
        data-support-surface="prepared-chat"
        data-presentation-surface="editorial"
      >
        <PresentationAssistantPane phase={beatId} />
        <div className="prepared-lifecycle-scene__presentation">
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
        </div>
      </section>
    </>
  );
};
