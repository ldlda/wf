import type { DemoTimelineController } from "../demo/useDemoTimeline.js";
import {
  discussionBranches,
  findBeat,
  findScene,
  type PresentationLocation,
  type SceneDefinition,
  type SceneBeatDefinition,
} from "./storyboard.js";
import { DemoWorkflowScene } from "./DemoWorkflowScene.js";
import { StageCaption } from "./StageCaption.js";
import { ArchitectureScene } from "./scenes/ArchitectureScene.js";

type SceneBodyProps = {
  readonly location: PresentationLocation;
  readonly demo: DemoTimelineController;
  readonly selectedNodeId: string | null;
  readonly selectNode: (nodeId: string | null) => void;
  readonly openEvidence: () => void;
  readonly openDiscussion: (branchId: string) => void;
  readonly onFocusPathChange: (path: readonly string[]) => void;
  readonly motionDisabled: boolean;
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
    <div className="scene-body__discussion-links" aria-label="discussion topics">
      {branches.map((branch) => (
        <button
          key={branch.id}
          type="button"
          onClick={() => openDiscussion(branch.id)}
        >
          {branch.title}
        </button>
      ))}
    </div>
  );
};

const NarrativeScene = ({ scene, beat }: { scene: SceneDefinition; beat: SceneBeatDefinition }) => (
  <>
    <StageCaption eyebrow={`Act ${scene.stageTheme === "paper" ? "I" : "II"} · ${scene.claimClass}`} title={scene.title}>
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
          <p>Typed workflow substrate for external agents and human operators.</p>
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
            <li>Chooses public operations</li>
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
            <li>Records traces and resume state</li>
          </ul>
        </section>
      </div>
      <p className="scene-body__evidence">{scene.evidencePointer}</p>
    </>
  );
};

const lifecycleStages = [
  { id: "draft", label: "Draft" },
  { id: "artifact", label: "Artifact" },
  { id: "deployment", label: "Deployment" },
  { id: "run", label: "Run" },
];

const LifecycleScene = ({ scene, beat }: { scene: SceneDefinition; beat: SceneBeatDefinition }) => (
  <>
    <StageCaption eyebrow="Act II · implemented" title={scene.title}>
      <p>{beat.caption}</p>
    </StageCaption>
    <div className="scene-body__lifecycle">
      {lifecycleStages.map((stage, i) => (
        <div
          key={stage.id}
          className={`scene-body__lifecycle-stage${beat.id === stage.id ? " scene-body__lifecycle-stage--active" : ""}`}
        >
          <span className="scene-body__lifecycle-number">{i + 1}</span>
          <strong>{stage.label}</strong>
          {i < lifecycleStages.length - 1 && <span className="scene-body__lifecycle-arrow">→</span>}
        </div>
      ))}
    </div>
    <p className="scene-body__evidence">{scene.evidencePointer}</p>
  </>
);

const authoringSteps = [
  { id: "discover", label: "Discover capability", detail: "wf schema / cap inspect" },
  { id: "author", label: "Author draft", detail: "wf draft create / add-step / bind" },
  { id: "diagnose", label: "Validate and diagnose", detail: "structured diagnostics + repair hints" },
  { id: "repair", label: "Repair", detail: "focused edit, no full rewrite" },
  { id: "compile", label: "Compile or save", detail: "artifact / deployment / run" },
] as const;

const AuthoringScene = ({ scene, beat }: { scene: SceneDefinition; beat: SceneBeatDefinition }) => (
  <>
    <StageCaption eyebrow="Act II · implemented" title={scene.title}>
      <p>{beat.caption}</p>
    </StageCaption>
    <div
      className="scene-body__authoring-loop"
      aria-label="agent authoring loop"
      data-active-stage={beat.id}
      data-readable-surface="dark"
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
            data-readable-surface="dark"
          >
            <span className="scene-body__authoring-number">{i + 1}</span>
            <strong>{step.label}</strong>
            <small>{step.detail}</small>
          </div>
        );
      })}
    </div>
    <p className="scene-body__evidence">{scene.evidencePointer}</p>
  </>
);

const evaluationStats = [
  { id: "cohort", value: "36", label: "trials" },
  { id: "validity", value: "2", label: "challenges" },
  { id: "findings", value: "3", label: "waves" },
];

const EvaluationScene = ({ scene, beat }: { scene: SceneDefinition; beat: SceneBeatDefinition }) => (
  <>
    <StageCaption eyebrow={`Act I · ${scene.claimClass}`} title={scene.title}>
      <p>{beat.caption}</p>
    </StageCaption>
    <div className="scene-body__evaluation">
      {evaluationStats.map((stat) => (
        <div
          key={stat.id}
          className={`scene-body__evaluation-stat${beat.id === stat.id ? " scene-body__evaluation-stat--active" : ""}`}
        >
          <strong>{stat.value}</strong>
          <span>{stat.label}</span>
        </div>
      ))}
    </div>
    <p className="scene-body__evidence">{scene.evidencePointer}</p>
  </>
);

const AgentHandoffScene = ({ scene, beat }: { scene: SceneDefinition; beat: SceneBeatDefinition }) => (
  <>
    <StageCaption eyebrow="Agent handoff" title={scene.title}>
      <p>{beat.caption}</p>
    </StageCaption>
    <p className="scene-body__evidence">{scene.evidencePointer}</p>
  </>
);

const assertNever = (value: never): never => {
  throw new Error(`Unexpected view: ${value}`);
};

export const SceneBody = ({ location, demo, selectedNodeId, selectNode, openEvidence, openDiscussion, onFocusPathChange, motionDisabled }: SceneBodyProps) => {
  const sceneId = location.kind === "main" ? location.sceneId : "positioning";
  const beatId = location.kind === "main" ? location.beatId : "landscape";
  const scene = findScene(sceneId) ?? findScene("thesis")!;
  const beat = findBeat(sceneId, beatId) ?? scene.beats[0]!;

  const discussionLinks = <DiscussionLinks sceneId={scene.id} openDiscussion={openDiscussion} />;
  const content = (() => {
  switch (scene.view) {
    case "narrative":
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
    case "demo":
      return (
        <DemoWorkflowScene
          scene={scene}
          beat={beat}
          demo={demo}
          selectedNodeId={selectedNodeId}
          selectNode={selectNode}
          openEvidence={openEvidence}
        />
      );
    case "evaluation":
      return <EvaluationScene scene={scene} beat={beat} />;
    case "conclusion":
      return <NarrativeScene scene={scene} beat={beat} />;
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
