import { StageCaption } from "../StageCaption.js";
import type { SceneBeatDefinition, SceneDefinition } from "../storyboard.js";
import { ConceptNode, ConceptRail } from "./ConceptPrimitives.js";

const toolLoopTurns = [
  {
    kind: "user",
    label: "User",
    detail: "Can you finish this workspace task?",
  },
  {
    kind: "assistant",
    label: "Assistant",
    detail: "Plans the next direct action.",
  },
  {
    kind: "tool",
    label: "Tool call",
    detail: "Runs one operation against the workspace.",
  },
  {
    kind: "observation",
    label: "Observation",
    detail: "Reads the result and decides what to do next.",
  },
  {
    kind: "answer",
    label: "Answer",
    detail: "Reports success, but leaves no reusable workflow behind.",
  },
] as const;

const automationProof = ["schemas", "bindings", "records"] as const;

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
      <section className="problem-loop-scene" aria-label="chat tool loop versus reusable automation">
        <article
          className="problem-chat-card"
          data-problem-active={automationBeat ? "false" : "true"}
          aria-label="one-off chat and tool loop"
        >
          <header className="problem-artifact-header">
            <span>One-off</span>
            <h2>Chat + tool loop</h2>
            <p>Good at getting through one request.</p>
          </header>
          <ol className="problem-chat-transcript" aria-label="one-off chat and tool transcript">
            {toolLoopTurns.map((turn) => (
              <li key={turn.kind} className="problem-chat-turn" data-turn-kind={turn.kind}>
                <span className="problem-chat-turn__label">{turn.label}</span>
                <p>{turn.detail}</p>
              </li>
            ))}
          </ol>
          <p className="problem-artifact-note">The useful work lives in the conversation history.</p>
        </article>

        <div className="problem-loop-scene__bridge" aria-hidden="true">→</div>

        <article
          className="problem-blueprint"
          role="group"
          aria-label="durable workflow blueprint"
          data-blueprint-active={automationBeat ? "true" : "false"}
        >
          <header className="problem-artifact-header">
            <span>Reusable</span>
            <h2>Workflow blueprint</h2>
            <p>Good at preserving how the work should run again.</p>
          </header>
          <ConceptRail label="Reusable automation">
            <ConceptNode title="design" icon="design" emphasis={automationBeat ? "primary" : "normal"} />
            <ConceptNode title="save" icon="save" emphasis={automationBeat ? "primary" : "normal"} />
            <ConceptNode title="connect" icon="connect" emphasis={automationBeat ? "primary" : "normal"} />
            <ConceptNode title="run" icon="run" emphasis={automationBeat ? "primary" : "normal"} />
            <ConceptNode title="inspect" icon="inspect" emphasis={automationBeat ? "primary" : "normal"} />
          </ConceptRail>
          <ul className="problem-blueprint__proof" aria-label="reusable automation proof points">
            {automationProof.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </article>
      </section>
      <p className="scene-body__evidence">{scene.evidencePointer}</p>
    </>
  );
};
