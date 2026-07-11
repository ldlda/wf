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
      <section
        className="opening-thesis-scene"
        aria-label="thesis opening"
        data-opening-focus={contributionBeat ? "contribution" : "title"}
      >
        <StageCaption eyebrow="Title" title={title}>
          <p>{beat.caption}</p>
        </StageCaption>
        <div
          className="opening-thesis"
          data-opening-beat={beat.id}
          data-opening-focus={contributionBeat ? "contribution" : "title"}
        >
          <header className="opening-thesis__statement">
            <p>Product goal</p>
            <h2>An AI Agent for Workspace Workflows</h2>
          </header>
          <ConceptRail label="AI agent roles" className="opening-thesis__agent-system">
            <ConceptNode
              title="Planner"
              subtitle="Codex, Claude, OpenCode"
              icon="planner"
            />
            <ConceptNode
              title="Tool surface"
              subtitle="CLI, MCP, JSON-RPC"
              icon="tool"
            />
            <ConceptNode
              title="Runner / platform"
              subtitle="Workflow lifecycle and deterministic execution"
              icon="platform"
              emphasis={contributionBeat ? "primary" : "normal"}
            >
              {contributionBeat ? (
                <>
                  <span>Implemented contribution</span>
                  <span>Lifecycle, validation, records, traces, and interrupt/resume</span>
                </>
              ) : null}
            </ConceptNode>
          </ConceptRail>
        </div>
      </section>
      <p className="scene-body__evidence">{scene.evidencePointer}</p>
    </>
  );
};
