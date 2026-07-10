import type { FC } from "react";
import { Bot, CalendarClock, ChartNoAxesCombined, ShieldCheck, Workflow, type LucideProps } from "lucide-react";
import { StageCaption } from "../StageCaption.js";
import type { SceneBeatDefinition, SceneDefinition } from "../storyboard.js";
import {
  contributionNodes,
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
      <section className="conclusion-map" aria-label="thesis contribution boundary" data-conclusion-beat={beatId}>
        <div className="conclusion-map__flow" aria-label="contribution flow">
          {contributionNodes.map((node, index) => (
            <div
              className={`conclusion-map__node conclusion-map__node--${node.id}`}
              data-node-id={node.id}
              data-emphasis={node.id === "substrate" ? "substrate" : "neutral"}
              key={node.id}
            >
              <span className="conclusion-map__node-index">0{index + 1}</span>
              <strong>{node.label}</strong>
              {node.id === "evidence" && <small>saved traces and receipts</small>}
            </div>
          ))}
        </div>

        <ul
          className="conclusion-map__non-claims"
          aria-label="explicit non-claims"
          data-emphasis={beatId === "limits" ? "limits" : "neutral"}
        >
          {nonClaims.map((claim) => <li key={claim}>{claim}</li>)}
        </ul>

        <ul className="conclusion-map__future" aria-label="future work layers" data-state={futureState}>
          {futureWorkBranches.map((branch) => {
            const Icon = futureWorkIcons[branch.icon];
            return (
              <li key={branch.id} data-future-work-id={branch.id}>
                <Icon aria-hidden="true" />
                <span>
                  <strong>{branch.label}</strong>
                  <small>{branch.example}</small>
                </span>
              </li>
            );
          })}
        </ul>

        <p className="conclusion-map__statement">Planner proposes; runtime executes.</p>
      </section>
      <p className="scene-body__evidence">{scene.evidencePointer}</p>
    </>
  );
};
