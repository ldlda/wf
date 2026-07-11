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
import { AuthoringPhaseVisual } from "./authoring/AuthoringPhaseVisual.js";
import { projectPreparedAuthoringPhase } from "./authoring/authoring-projection.js";
import type { AuthoringPhaseId } from "./authoring/authoring-recording.js";
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
};

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

const PositioningScene = ({ scene, beat }: { scene: SceneDefinition; beat: SceneBeatDefinition }) => {
  const highlightLda = beat.id === "lda-position";
  return (
    <>
      <StageCaption eyebrow={`Act I · ${scene.claimClass}`} title={scene.title}>
        <p>{beat.caption}</p>
      </StageCaption>
      <div
        className="scene-body__positioning-map"
        aria-label="positioning map"
        data-positioning-active-region={highlightLda ? "lda" : "landscape"}
      >
        <section className="scene-body__positioning-column" aria-label="direct action patterns">
          <p className="scene-body__positioning-label">Direct action</p>
          <article className="scene-body__positioning-tile">
            <strong>Tool loops</strong>
            <span>Fast action, no durable lifecycle</span>
          </article>
          <article className="scene-body__positioning-tile">
            <strong>Generated scripts</strong>
            <span>Inspectable code, weak deployment records</span>
          </article>
        </section>
        <article
          className="scene-body__positioning-substrate"
          data-positioning-role="substrate"
          data-positioning-active={highlightLda ? "true" : "false"}
        >
          <span className="scene-body__positioning-label">This thesis</span>
          <strong>lda.chat</strong>
          <p>Typed lifecycle substrate for external agents and human operators.</p>
          <ul>
            <li>Lifecycle</li>
            <li>Validation</li>
            <li>Persisted records</li>
          </ul>
        </article>
        <section className="scene-body__positioning-column" aria-label="adjacent systems">
          <p className="scene-body__positioning-label">Adjacent systems</p>
          <article className="scene-body__positioning-tile">
            <strong>Hosted automation</strong>
            <span>Managed triggers and app integrations</span>
          </article>
          <article className="scene-body__positioning-tile">
            <strong>Agent graphs</strong>
            <span>Durable planner loops</span>
          </article>
          <article className="scene-body__positioning-tile">
            <strong>MCP</strong>
            <span>Capability protocol boundary</span>
          </article>
        </section>
      </div>
      <p className="scene-body__evidence">{scene.evidencePointer}</p>
    </>
  );
};

const boundaryActiveForBeat = (beatId: string): "planner" | "runtime" | "boundary" => {
  if (beatId === "runtime") return "runtime";
  if (beatId === "boundary") return "boundary";
  return "planner";
};

const BoundaryScene = ({ scene, beat }: { scene: SceneDefinition; beat: SceneBeatDefinition }) => {
  const active = boundaryActiveForBeat(beat.id);
  const plannerActive = active === "planner" || active === "boundary";
  const runtimeActive = active === "runtime" || active === "boundary";
  return (
    <>
      <StageCaption eyebrow="Act II · implemented" title={scene.title}>
        <p>{beat.caption}</p>
      </StageCaption>
      <div className="scene-body__boundary" aria-label="planner runtime boundary" data-boundary-active={active}>
        <section
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
        </section>
        <div className="scene-body__boundary-seam" aria-label="workflow operation boundary">
          <strong>CLI / JSON-RPC</strong>
          <span>typed workflow operations</span>
        </div>
        <section
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
        </section>
      </div>
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

const LifecycleScene = ({ scene, beat }: { scene: SceneDefinition; beat: SceneBeatDefinition }) => {
  const activeIndex = Math.max(0, lifecycleStages.findIndex((stage) => stage.id === beat.id));
  const activeStage = lifecycleStages[activeIndex]!;
  return (
    <>
      <StageCaption eyebrow="Act II · implemented" title={scene.title}>
        <p>{beat.caption}</p>
      </StageCaption>
      <div className="scene-body__lifecycle" aria-label="workflow lifecycle rail" data-lifecycle-active-stage={activeStage.id}>
        {lifecycleStages.map((stage, i) => (
          <article
            key={stage.id}
            className="scene-body__lifecycle-stage"
            data-lifecycle-active={i === activeIndex ? "true" : "false"}
            data-lifecycle-complete={i < activeIndex ? "true" : "false"}
          >
            <span className="scene-body__lifecycle-number">{i + 1}</span>
            <strong>{stage.label}</strong>
            <small>{stage.role}</small>
            {i < lifecycleStages.length - 1 && <span className="scene-body__lifecycle-arrow">→</span>}
          </article>
        ))}
      </div>
      <aside className="scene-body__lifecycle-current" aria-label="current lifecycle state">
        <span>{activeStage.label}</span>
        <strong>{activeStage.role}</strong>
        <p>{activeStage.detail}</p>
      </aside>
      <p className="scene-body__evidence">{scene.evidencePointer}</p>
    </>
  );
};

const authoringSteps = [
  { id: "discover", label: "Discover capability", detail: "wf schema / cap inspect" },
  { id: "author", label: "Author draft", detail: "wf draft create / add-step / bind" },
  { id: "diagnose", label: "Validate and diagnose", detail: "structured diagnostics + repair hints" },
  { id: "repair", label: "Repair", detail: "focused edit, no full rewrite" },
  { id: "compile", label: "Compile or save", detail: "artifact / deployment / run" },
] as const;

// Scene 7 uses speaker-friendly beat names; the prepared recording keeps the
// underlying product phases (`draft` and `validate`) as its canonical IDs.
const authoringPhaseForBeat = (beatId: string): AuthoringPhaseId => {
  if (beatId === "author") return "draft";
  if (beatId === "diagnose" || beatId === "repair") return "validate";
  return beatId as AuthoringPhaseId;
};

const AuthoringScene = ({ scene, beat }: { scene: SceneDefinition; beat: SceneBeatDefinition }) => {
  const projection = projectPreparedAuthoringPhase(authoringPhaseForBeat(beat.id));
  const primaryCommand = projection.commands[0];
  // The prepared recording is the factual source for this public-operation label.
  if (!primaryCommand) throw new Error(`Authoring phase ${projection.phase} has no public operation`);

  return (
    <>
      <StageCaption eyebrow="Act II · implemented" title={scene.title}>
        <p>{beat.caption}</p>
      </StageCaption>
      <section
        className="scene-body__authoring-composition"
        aria-label="agent authoring loop"
        data-active-stage={beat.id}
        data-presentation-surface="editorial"
      >
        <article className="scene-body__authoring-evidence" aria-label={`${projection.label} product evidence`}>
          <header>
            <span>Public operation</span>
            <strong>{primaryCommand.title}</strong>
            <p>{projection.summary}</p>
          </header>
          <AuthoringPhaseVisual projection={projection} />
        </article>
        <div
          className="scene-body__authoring-loop"
          aria-label="authoring phase loop"
        >
          <div className="scene-body__authoring-loop-rail" aria-hidden="true" />
          {authoringSteps.map((step, i) => {
            const isActive = beat.id === step.id;
            const isPast = authoringSteps.findIndex((candidate) => candidate.id === beat.id) > i;
            return (
              <div
                key={step.id}
                className="scene-body__authoring-node"
                data-authoring-active={isActive}
                data-authoring-past={isPast}
              >
                <span className="scene-body__authoring-number">{i + 1}</span>
                <strong>{step.label}</strong>
                <small>{step.detail}</small>
              </div>
            );
          })}
        </div>
      </section>
      <p className="scene-body__evidence">{scene.evidencePointer}</p>
    </>
  );
};

const assertNever = (value: never): never => {
  throw new Error(`Unexpected view: ${value}`);
};

export const SceneBody = ({ location, demo, timelineAgent, selectedNodeId, selectNode, openEvidence, openDiscussion, onFocusPathChange, motionDisabled, approvalActions }: SceneBodyProps) => {
  const sceneId = location.kind === "main" ? location.sceneId : "positioning";
  const beatId = location.kind === "main" ? location.beatId : "landscape";
  const scene = findScene(sceneId) ?? findScene("thesis")!;
  const beat = findBeat(sceneId, beatId) ?? scene.beats[0]!;

  // The questions beat renders its own grouped discussion index. Suppress the
  // generic per-scene rail there so the same actions do not appear twice.
  const showDiscussionRail = !(scene.id === "conclusion" && beat.id === "questions");
  const discussionLinks = showDiscussionRail ? <DiscussionLinks sceneId={scene.id} openDiscussion={openDiscussion} /> : null;
  const content = (() => {
  switch (scene.view) {
    case "narrative":
      if (scene.id === "thesis") return <OpeningThesisScene scene={scene} beat={beat} />;
      if (scene.id === "problem") return <ProblemLoopScene scene={scene} beat={beat} />;
      return <NarrativeScene scene={scene} beat={beat} />;
    case "positioning":
      return <PositioningScene scene={scene} beat={beat} />;
    case "boundary":
      return <BoundaryScene scene={scene} beat={beat} />;
    case "lifecycle":
      return <LifecycleScene scene={scene} beat={beat} />;
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
    case "authoring":
      return <AuthoringScene scene={scene} beat={beat} />;
    case "agent":
      return <AgentHandoffScene scene={scene} beat={beat} />;
      case "demo-lifecycle":
      return <PreparedAuthoringLifecycleScene scene={scene} beat={beat} />;
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
      {discussionLinks}
    </>
  );
};
