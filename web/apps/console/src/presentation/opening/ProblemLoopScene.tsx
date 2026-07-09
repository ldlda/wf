import { StageCaption } from "../StageCaption.js";
import type { SceneBeatDefinition, SceneDefinition } from "../storyboard.js";
import { ConceptNode, ConceptRail } from "./ConceptPrimitives.js";

const toolLoopTurns = [
  { role: "User prompt", detail: "Do this workspace task once." },
  { role: "Agent reasoning", detail: "Decides the next action." },
  { role: "Tool call", detail: "Runs an operation directly." },
  { role: "Observation", detail: "Reads the result." },
  { role: "Final answer", detail: "Reports success, but keeps no reusable lifecycle." },
] as const;

type ProblemLoopSceneProps = {
  readonly scene: SceneDefinition;
  readonly beat: SceneBeatDefinition;
};

export const ProblemLoopScene = ({ scene, beat }: ProblemLoopSceneProps) => {
  const automationBeat = beat.id === "missing-contracts";
  return (
    <>
      <StageCaption eyebrow="Problem shape" title={scene.title}>
        <p>{beat.caption}</p>
      </StageCaption>
      <section className="problem-loop-scene" aria-label="action sequence versus reusable automation">
        <div
          className="problem-loop-scene__side problem-loop-scene__side--transcript"
          data-problem-active={automationBeat ? "false" : "true"}
        >
          <h2>One-off tool loop</h2>
          <ol className="problem-loop-transcript" aria-label="one-off tool loop transcript">
            {toolLoopTurns.map((turn) => (
              <li key={turn.role} className="problem-loop-transcript__turn">
                <span>{turn.role}</span>
                <p>{turn.detail}</p>
              </li>
            ))}
          </ol>
          <p>Useful once. Hard to reuse.</p>
        </div>

        <div className="problem-loop-scene__bridge" aria-hidden="true">→</div>

        <div className="problem-loop-scene__side" data-problem-active={automationBeat ? "true" : "false"}>
          <h2>Reusable automation</h2>
          <ConceptRail label="Reusable automation">
            <ConceptNode title="design" icon="design" emphasis={automationBeat ? "primary" : "normal"} />
            <ConceptNode title="save" icon="save" emphasis={automationBeat ? "primary" : "normal"} />
            <ConceptNode title="connect" icon="connect" emphasis={automationBeat ? "primary" : "normal"} />
            <ConceptNode title="run" icon="run" emphasis={automationBeat ? "primary" : "normal"} />
            <ConceptNode title="inspect" icon="inspect" emphasis={automationBeat ? "primary" : "normal"} />
          </ConceptRail>
          <p>The platform makes work reusable.</p>
        </div>
      </section>
      <p className="scene-body__evidence">{scene.evidencePointer}</p>
    </>
  );
};
