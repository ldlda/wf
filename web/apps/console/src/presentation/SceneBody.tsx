import { m } from "motion/react";
import type { DemoTimelineController } from "../demo/useDemoTimeline.js";
import type { TimelineAgentController } from "../demo/agent/timelineAgent.js";
import type { DemoApprovalActions } from "./demo-approval-actions.js";
import { AgentHandoffScene } from "./authoring/AgentHandoffScene.js";
import {
  discussionBranches,
  findBeat,
  findScene,
  type PresentationLocation,
  type SceneDefinition,
  type SceneBeatDefinition,
} from "./storyboard.js";
import { PreparedAuthoringLifecycleScene } from "./authoring/PreparedAuthoringLifecycleScene.js";
import { DemoWorkflowScene } from "./DemoWorkflowScene.js";
import { StageCaption } from "./StageCaption.js";
import { ConclusionScene } from "./conclusion/ConclusionScene.js";
import { DefenseDiscussionIndex } from "./discussion/DefenseDiscussionIndex.js";
import { EvaluationEvidenceScene } from "./evaluation/EvaluationEvidenceScene.js";
import { ArchitectureScene } from "./scenes/ArchitectureScene.js";
import { OpeningThesisScene } from "./opening/OpeningThesisScene.js";
import { ProblemLoopScene } from "./opening/ProblemLoopScene.js";

type SceneBodyProps = {
  readonly location: PresentationLocation;
  readonly demo: DemoTimelineController;
  readonly timelineAgent?: TimelineAgentController | undefined;
  readonly selectedNodeId: string | null;
  readonly selectNode: (nodeId: string | null) => void;
  readonly openEvidence: () => void;
  readonly openDiscussion: (branchId: string) => void;
  readonly onFocusPathChange: (path: readonly string[]) => void;
  readonly motionDisabled: boolean;
  readonly approvalActions?: DemoApprovalActions | undefined;
  readonly onPreparedLifecycleAdvance?: (() => void) | undefined;
};

const workflowDemoSceneIds = new Set([
  "prepared-lifecycle",
  "run-from-deployment",
  "typed-human-boundary",
  "resume-output-evidence",
]);

const DiscussionLinks = ({
  sceneId,
  openDiscussion,
}: {
  readonly sceneId: string;
  readonly openDiscussion: (branchId: string) => void;
}) => {
  const branches = discussionBranches.filter((branch) => branch.parentSceneId === sceneId);
  if (branches.length === 0) return null;
  return (
    <aside className="scene-body__discussion-links" aria-label="defense discussion topics" data-discussion-rail="true">
      <span className="scene-body__discussion-label">Defense questions</span>
      <ul className="scene-body__discussion-list">
        {branches.map((branch) => (
          <li key={branch.id}>
            <button
              type="button"
              onClick={() => openDiscussion(branch.id)}
            >
              <span>{branch.title}</span> <small>{branch.claimClass}</small>
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
};

const actForSceneNumber = (sceneNumber: number): string => {
  if (sceneNumber <= 3) return "I";
  if (sceneNumber <= 12) return "II";
  if (sceneNumber === 13) return "III";
  return "IV";
};

const NarrativeScene = ({ scene, beat }: { scene: SceneDefinition; beat: SceneBeatDefinition }) => (
  <>
    <StageCaption eyebrow={`Act ${actForSceneNumber(scene.number)} · ${scene.claimClass}`} title={scene.title}>
      <p>{beat.caption}</p>
    </StageCaption>
    <p className="scene-body__evidence">{scene.evidencePointer}</p>
  </>
);

const choreographyTransition = (motionDisabled: boolean) => ({
  duration: motionDisabled ? 0 : 0.34,
  ease: [0.16, 1, 0.3, 1] as const,
});

type ChoreographyProps = {
  readonly scene: SceneDefinition;
  readonly beat: SceneBeatDefinition;
  readonly motionDisabled: boolean;
};

const PositioningScene = ({ scene, beat, motionDisabled }: ChoreographyProps) => {
  const highlightLda = beat.id === "lda-position";
  const transition = choreographyTransition(motionDisabled);
  return (
    <>
      <StageCaption eyebrow={`Act I · ${scene.claimClass}`} title={scene.title}>
        <p>{beat.caption}</p>
      </StageCaption>
      <m.div
        layout
        className="scene-body__positioning-map"
        aria-label="positioning map"
        data-positioning-active-region={highlightLda ? "lda" : "landscape"}
        data-visual-role="primary"
        data-motion={motionDisabled ? "disabled" : "enabled"}
        transition={transition}
      >
        <m.section layout transition={transition} className="scene-body__positioning-column" aria-label="direct action patterns">
          <p className="scene-body__positioning-label">Direct action</p>
          <m.article layout transition={transition} className="scene-body__positioning-tile">
            <strong>Tool loops</strong>
            <span>Fast action, no durable lifecycle</span>
          </m.article>
          <m.article layout transition={transition} className="scene-body__positioning-tile">
            <strong>Generated scripts</strong>
            <span>Inspectable code, weak deployment records</span>
          </m.article>
        </m.section>
        <m.article
          layout
          className="scene-body__positioning-substrate"
          data-positioning-role="substrate"
          data-positioning-active={highlightLda ? "true" : "false"}
          transition={transition}
        >
          <span className="scene-body__positioning-label">This thesis</span>
          <strong>lda.chat</strong>
          <p>Typed lifecycle substrate for external agents and human operators.</p>
          <ul>
            <li>Lifecycle</li>
            <li>Validation</li>
            <li>Persisted records</li>
          </ul>
        </m.article>
        <m.section layout transition={transition} className="scene-body__positioning-column" aria-label="adjacent systems">
          <p className="scene-body__positioning-label">Adjacent systems</p>
          <m.article layout transition={transition} className="scene-body__positioning-tile">
            <strong>Hosted automation</strong>
            <span>Managed triggers and app integrations</span>
          </m.article>
          <m.article layout transition={transition} className="scene-body__positioning-tile">
            <strong>Agent graphs</strong>
            <span>Durable planner loops</span>
          </m.article>
          <m.article layout transition={transition} className="scene-body__positioning-tile">
            <strong>MCP</strong>
            <span>Capability protocol boundary</span>
          </m.article>
        </m.section>
      </m.div>
      <p className="scene-body__evidence">{scene.evidencePointer}</p>
    </>
  );
};

const boundaryActiveForBeat = (beatId: string): "planner" | "runtime" | "boundary" => {
  if (beatId === "runtime") return "runtime";
  if (beatId === "boundary") return "boundary";
  return "planner";
};

const BoundaryScene = ({ scene, beat, motionDisabled }: ChoreographyProps) => {
  const active = boundaryActiveForBeat(beat.id);
  const plannerActive = active === "planner" || active === "boundary";
  const runtimeActive = active === "runtime" || active === "boundary";
  const transition = choreographyTransition(motionDisabled);
  return (
    <>
      <StageCaption eyebrow="Act II · implemented" title={scene.title}>
        <p>{beat.caption}</p>
      </StageCaption>
      <m.div
        layout
        className="scene-body__boundary"
        aria-label="planner runtime boundary"
        data-boundary-active={active}
        data-visual-role="primary"
        data-motion={motionDisabled ? "disabled" : "enabled"}
        transition={transition}
      >
        <m.section
          layout
          transition={transition}
          className="scene-body__boundary-pane"
          data-boundary-side="planner"
          data-boundary-emphasis={plannerActive ? "active" : "reduced"}
        >
          <span>External operator</span>
          <h3>Planner</h3>
          <ul>
            <li>Proposes workflow structure</li>
            <li>Revises steps and bindings</li>
            <li>Chooses tools</li>
          </ul>
        </m.section>
        <m.div layout transition={transition} className="scene-body__boundary-seam" aria-label="workflow operation boundary">
          <strong>CLI / JSON-RPC</strong>
          <span>typed workflow operations</span>
        </m.div>
        <m.section
          layout
          transition={transition}
          className="scene-body__boundary-pane"
          data-boundary-side="runtime"
          data-boundary-emphasis={runtimeActive ? "active" : "reduced"}
        >
          <span>lda.chat substrate</span>
          <h3>Runtime</h3>
          <ul>
            <li>Validates schemas and routes</li>
            <li>Executes deterministic nodes</li>
            <li>Records traces and run output</li>
            <li>Resumes from persisted state</li>
          </ul>
        </m.section>
      </m.div>
      <p className="scene-body__evidence">{scene.evidencePointer}</p>
    </>
  );
};

const lifecycleStages = [
  { id: "draft", label: "Draft", role: "Mutable authoring state", detail: "Iterate before freezing a workflow definition." },
  { id: "artifact", label: "Artifact", role: "Immutable workflow definition", detail: "Save a versioned plan that can be deployed." },
  { id: "deployment", label: "Deployment", role: "Source binding", detail: "Bind workflow requirements to configured runtime sources." },
  { id: "run", label: "Run", role: "Execution record and trace", detail: "Persist status, outputs, interrupts, and trace evidence." },
] as const;

const LifecycleScene = ({ scene, beat, motionDisabled }: ChoreographyProps) => {
  const activeIndex = Math.max(0, lifecycleStages.findIndex((stage) => stage.id === beat.id));
  const activeStage = lifecycleStages[activeIndex]!;
  const transition = choreographyTransition(motionDisabled);
  return (
    <>
      <StageCaption eyebrow="Act II · implemented" title={scene.title}>
        <p>{beat.caption}</p>
      </StageCaption>
      <m.div
        layout
        className="scene-body__lifecycle"
        aria-label="workflow lifecycle rail"
        data-lifecycle-active-stage={activeStage.id}
        data-visual-role="primary"
        data-motion={motionDisabled ? "disabled" : "enabled"}
        transition={transition}
      >
        {lifecycleStages.map((stage, i) => (
          <m.article
            layout
            transition={transition}
            key={stage.id}
            className="scene-body__lifecycle-stage"
            data-lifecycle-active={i === activeIndex ? "true" : "false"}
            data-lifecycle-complete={i < activeIndex ? "true" : "false"}
          >
            <span className="scene-body__lifecycle-number">{i + 1}</span>
            <strong>{stage.label}</strong>
            <small>{stage.role}</small>
            {i < lifecycleStages.length - 1 && <span className="scene-body__lifecycle-arrow">→</span>}
          </m.article>
        ))}
      </m.div>
      <aside className="scene-body__lifecycle-current" aria-label="current lifecycle state">
        <span>{activeStage.label}</span>
        <strong>{activeStage.role}</strong>
        <p>{activeStage.detail}</p>
        {activeStage.id === "artifact" && (
          <div className="scene-body__lifecycle-optional" aria-label="optional artifact path">
            <span>Optional evidence path</span>
            <strong>Raw plan -&gt; artifact</strong>
            <p>A plan can be compiled into an immutable version; Draft is not mandatory.</p>
          </div>
        )}
      </aside>
      <p className="scene-body__evidence">{scene.evidencePointer}</p>
    </>
  );
};

const assertNever = (value: never): never => {
  throw new Error(`Unexpected view: ${value}`);
};

export const SceneBody = ({ location, demo, selectedNodeId, selectNode, openEvidence, openDiscussion, onFocusPathChange, motionDisabled, approvalActions, onPreparedLifecycleAdvance }: SceneBodyProps) => {
  const sceneId = location.kind === "main" ? location.sceneId : "positioning";
  const beatId = location.kind === "main" ? location.beatId : "landscape";
  const scene = findScene(sceneId) ?? findScene("thesis")!;
  const beat = findBeat(sceneId, beatId) ?? scene.beats[0]!;

  const isWorkflowDemoScene = workflowDemoSceneIds.has(scene.id);
  const showDiscussionRail = !(scene.id === "conclusion" && beat.id === "questions")
    && (!isWorkflowDemoScene || scene.id === "prepared-lifecycle");
  const discussionLinks = showDiscussionRail ? <DiscussionLinks sceneId={scene.id} openDiscussion={openDiscussion} /> : null;
  const content = (() => {
  switch (scene.view) {
    case "narrative":
      if (scene.id === "thesis") return <OpeningThesisScene scene={scene} beat={beat} />;
      if (scene.id === "problem") return <ProblemLoopScene scene={scene} beat={beat} />;
      return <NarrativeScene scene={scene} beat={beat} />;
    case "positioning":
      return <PositioningScene scene={scene} beat={beat} motionDisabled={motionDisabled} />;
    case "boundary":
      return <BoundaryScene scene={scene} beat={beat} motionDisabled={motionDisabled} />;
    case "lifecycle":
      return <LifecycleScene scene={scene} beat={beat} motionDisabled={motionDisabled} />;
    case "architecture":
      return (
        <ArchitectureScene
          scene={scene}
          beat={beat}
          focusPath={location.kind === "main" ? location.focusPath : []}
          activeNodeId={beat.figure?.activeNodeId ?? null}
          onFocusPathChange={onFocusPathChange}
          motionDisabled={motionDisabled}
        />
      );
    case "agent":
      return <AgentHandoffScene scene={scene} beat={beat} />;
    case "demo-lifecycle":
      return (
        <PreparedAuthoringLifecycleScene
          scene={scene}
          beat={beat}
          onAdvance={onPreparedLifecycleAdvance}
          discussionRail={scene.id === "prepared-lifecycle" ? discussionLinks : undefined}
        />
      );
    case "demo":
      return (
        <DemoWorkflowScene
          scene={scene}
          beat={beat}
          demo={demo}
          selectedNodeId={selectedNodeId}
          selectNode={selectNode}
          openEvidence={openEvidence}
          approvalActions={approvalActions}
        />
      );
    case "evaluation":
      return <EvaluationEvidenceScene scene={scene} beat={beat} />;
    case "conclusion":
      return beat.id === "questions"
        ? <DefenseDiscussionIndex discussionBranches={discussionBranches} openDiscussion={openDiscussion} />
        : <ConclusionScene scene={scene} beat={beat} />;
    default:
      return assertNever(scene.view);
  }
  })();

  return (
    <>
      {content}
      {scene.id === "prepared-lifecycle" ? null : discussionLinks}
    </>
  );
};
