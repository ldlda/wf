import { useState } from "react";
import { projectPreparedAuthoringPhase } from "./authoring-projection.js";
import { AuthoringTracePanel } from "./AuthoringTracePanel.js";
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
 * sourced from the prepared authoring recording. A persistent "Agent trace"
 * trigger opens the AuthoringTracePanel overlay.
 *
 * The receipt bridges Scene 8's full conversation and Scene 9's separate
 * trace panel without morphing runtime-owned components.
 */
export const PreparedAuthoringLifecycleScene = ({ scene, beat }: PreparedAuthoringLifecycleSceneProps) => {
  const beatId = beat.id as AuthoringPhaseId;
  const [traceOpen, setTraceOpen] = useState(false);
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

        <article className="prepared-lifecycle-scene__projection">
          <div className="prepared-lifecycle-scene__summary">
            <p>{projection.summary}</p>
          </div>
          <div className="prepared-lifecycle-scene__commands">
            {projection.commands.map((cmd, i) => (
              <div key={i} className="prepared-lifecycle-scene__command">
                <code>$ {cmd.command}</code>
                <span className="prepared-lifecycle-scene__command-result" data-result={cmd.result}>
                  {cmd.result === "success" ? "✓" : "⚡"} {cmd.result}
                </span>
              </div>
            ))}
          </div>
        </article>
      </section>
      <div className="prepared-lifecycle-scene__receipt">
        <AuthoringTracePanel
          phase={beatId}
          open={traceOpen}
          onOpen={() => setTraceOpen(true)}
          onClose={() => setTraceOpen(false)}
        />
      </div>
    </>
  );
};
