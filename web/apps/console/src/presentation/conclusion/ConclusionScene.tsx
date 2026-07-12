import type { FC } from "react";
import { Bot, CalendarClock, ChartNoAxesCombined, ShieldCheck, Workflow, type LucideProps } from "lucide-react";
import { StageCaption } from "../StageCaption.js";
import type { SceneBeatDefinition, SceneDefinition } from "../storyboard.js";
import {
  contributionNodes,
  evidenceNode,
  futureWorkBranches,
  isConclusionBeatId,
  nonClaims,
  type FutureWorkIcon,
} from "./conclusion-model.js";

type ConclusionSceneProps = {
  readonly scene: SceneDefinition;
  readonly beat: SceneBeatDefinition;
};

const futureWorkIcons: Record<FutureWorkIcon, FC<LucideProps>> = {
  agent: Bot,
  security: ShieldCheck,
  schedule: CalendarClock,
  evaluation: ChartNoAxesCombined,
  runtime: Workflow,
};

export const ConclusionScene: FC<ConclusionSceneProps> = ({ scene, beat }) => {
  const beatId = isConclusionBeatId(beat.id) ? beat.id : "conclusion";
  const futureState = beatId === "conclusion" ? "receded" : "visible";

  return (
    <>
      <StageCaption eyebrow={`Act IV · ${scene.claimClass}`} title={scene.title}>
        <p>{beat.caption}</p>
      </StageCaption>
      <section
        className="conclusion-map"
        aria-label="thesis contribution boundary"
        data-conclusion-beat={beatId}
        data-visual-role="contribution-boundary"
      >
        <div className="conclusion-map__flow" aria-label="contribution flow">
          <div className="conclusion-map__flow-unit conclusion-map__flow-unit--planner" data-flow-unit="planner">
            <div
              className="conclusion-map__node conclusion-map__node--planner"
              data-node-id={contributionNodes[0].id}
              data-emphasis="neutral"
            >
              <span className="conclusion-map__node-index">01</span>
              <strong>{contributionNodes[0].label}</strong>
            </div>
          </div>
          <div className="conclusion-map__flow-unit conclusion-map__flow-unit--substrate-stack" data-flow-unit="substrate-stack">
            <div
              className="conclusion-map__node conclusion-map__node--substrate"
              data-node-id={contributionNodes[1].id}
              data-emphasis="substrate"
            >
              <span className="conclusion-map__node-index">02</span>
              <strong>{contributionNodes[1].label}</strong>
            </div>
            <div
              className={`conclusion-map__node conclusion-map__node--${evidenceNode.id}`}
              data-evidence-attachment="vertical"
              data-node-id={evidenceNode.id}
            >
              <span className="conclusion-map__node-index">04</span>
              <strong>{evidenceNode.label}</strong>
              <small>saved traces and receipts</small>
            </div>
          </div>
          <div className="conclusion-map__flow-unit conclusion-map__flow-unit--runtime" data-flow-unit="runtime">
            <div
              className="conclusion-map__node conclusion-map__node--runtime"
              data-node-id={contributionNodes[2].id}
              data-emphasis="neutral"
            >
              <span className="conclusion-map__node-index">03</span>
              <strong>{contributionNodes[2].label}</strong>
            </div>
          </div>
        </div>

        <ul
          className="conclusion-map__non-claims"
          aria-label="explicit non-claims"
          data-emphasis={beatId === "limits" ? "limits" : "neutral"}
          data-conclusion-support={beatId === "limits" ? "primary" : "receded"}
        >
          {nonClaims.map((claim) => <li key={claim}>{claim}</li>)}
        </ul>

        <ul
          className="conclusion-map__future"
          aria-label="future work layers"
          data-state={futureState}
          data-conclusion-support={beatId === "future" ? "primary" : "receded"}
        >
          {futureWorkBranches.map((branch) => {
            const Icon = futureWorkIcons[branch.icon];
            return (
              <li key={branch.id} data-future-work-id={branch.id}>
                <Icon aria-hidden="true" data-emphasis="neutral" />
                <span>
                  <strong>{branch.label}</strong>
                  <small>{branch.example}</small>
                </span>
              </li>
            );
          })}
        </ul>

        <p className="conclusion-map__statement" data-conclusion-support={beatId === "conclusion" ? "primary" : "receded"}>Planner proposes; runtime executes.</p>
      </section>
      <p className="scene-body__evidence">{scene.evidencePointer}</p>
    </>
  );
};
