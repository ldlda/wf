import { StageCaption } from "../StageCaption.js";
import type { SceneBeatDefinition, SceneDefinition } from "../storyboard.js";
import { ConceptNode, ConceptRail } from "./ConceptPrimitives.js";

type OpeningThesisSceneProps = {
  readonly scene: SceneDefinition;
  readonly beat: SceneBeatDefinition;
};

const title = "Design and Implementation of lda.chat";

export const OpeningThesisScene = ({ scene, beat }: OpeningThesisSceneProps) => {
  const contributionBeat = beat.id === "substrate";
  return (
    <>
      <StageCaption eyebrow="Origin story" title={title}>
        <p>{beat.caption}</p>
      </StageCaption>
      <section
        className="opening-thesis"
        aria-label="thesis opening"
        data-opening-beat={beat.id}
        data-opening-focus={contributionBeat ? "substrate" : "title"}
        data-support-state={contributionBeat ? "revealed" : "receded"}
      >
        <div className="opening-thesis__title-card" data-opening-role="title">
          <span>AI agent for workspace workflows</span>
          <strong>{contributionBeat ? "Decomposed" : scene.title}</strong>
        </div>
        <div className="opening-thesis__decomposition">
          <ConceptRail label="AI agent components">
            <ConceptNode
              title="Planner"
              subtitle="Codex / Claude / OpenCode"
              icon="planner"
              emphasis={contributionBeat ? "muted" : "normal"}
            />
            <ConceptNode
              title="Tool Surface"
              subtitle="CLI / MCP / APIs"
              icon="tool"
              emphasis={contributionBeat ? "muted" : "normal"}
            />
            <ConceptNode
              title="Workflow Platform"
              subtitle="submitted substrate"
              icon="platform"
              emphasis="primary"
            >
              <span>Typed · Durable · Inspectable</span>
            </ConceptNode>
          </ConceptRail>
        </div>
      </section>
      <p className="scene-body__evidence">{scene.evidencePointer}</p>
    </>
  );
};
