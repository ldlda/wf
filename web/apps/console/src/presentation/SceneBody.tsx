import type { DemoTimelineController } from "../demo/useDemoTimeline.js";
import { findBeat, findScene, type PresentationLocation, type SceneDefinition, type SceneBeatDefinition } from "./storyboard.js";
import { NodeSpotlight } from "./NodeSpotlight.js";
import { OperationBlock } from "./OperationBlock.js";
import { StageCaption } from "./StageCaption.js";
import { WorkflowGraphStage } from "./WorkflowGraphStage.js";

type SceneBodyProps = {
  readonly location: PresentationLocation;
  readonly demo: DemoTimelineController;
  readonly selectedNodeId: string | null;
  readonly selectNode: (nodeId: string) => void;
};

const operationStageByBeat: Readonly<Record<string, string | undefined>> = {
  operation: "run_start",
  interrupt: "interrupt",
  approval: "interrupt",
  resume: "run_resume",
  trace: "trace_read",
};

const NarrativeScene = ({ scene, beat }: { scene: SceneDefinition; beat: SceneBeatDefinition }) => (
  <>
    <StageCaption eyebrow={`Act ${scene.stageTheme === "paper" ? "I" : "II"} · ${scene.claimClass}`} title={scene.title}>
      <p>{beat.caption}</p>
    </StageCaption>
    <p className="scene-body__evidence">{scene.evidencePointer}</p>
  </>
);

const PositioningScene = ({ scene, beat }: { scene: SceneDefinition; beat: SceneBeatDefinition }) => (
  <>
    <StageCaption eyebrow={`Act I · ${scene.claimClass}`} title={scene.title}>
      <p>{beat.caption}</p>
    </StageCaption>
    <div className="scene-body__positioning-grid">
      <div className="scene-body__positioning-card">
        <strong>Tool loops</strong>
        <span>Direct action, no lifecycle</span>
      </div>
      <div className="scene-body__positioning-card">
        <strong>Scripts</strong>
        <span>Simple, debuggable</span>
      </div>
      <div className="scene-body__positioning-card scene-body__positioning-card--active">
        <strong>lda.chat</strong>
        <span>Typed lifecycle contracts</span>
      </div>
      <div className="scene-body__positioning-card">
        <strong>Agent graphs</strong>
        <span>Shared durability</span>
      </div>
      <div className="scene-body__positioning-card">
        <strong>MCP</strong>
        <span>Capability protocol</span>
      </div>
    </div>
    <p className="scene-body__evidence">{scene.evidencePointer}</p>
  </>
);

const BoundaryScene = ({ scene, beat }: { scene: SceneDefinition; beat: SceneBeatDefinition }) => (
  <>
    <StageCaption eyebrow="Act II · implemented" title={scene.title}>
      <p>{beat.caption}</p>
    </StageCaption>
    <div className="scene-body__boundary">
      <div className="scene-body__boundary-side">
        <h3>Planner</h3>
        <p>External LLM proposes and revises workflow structure.</p>
      </div>
      <div className="scene-body__boundary-divider" />
      <div className="scene-body__boundary-side">
        <h3>Runtime</h3>
        <p>Validates, executes, records, and resumes deterministically.</p>
      </div>
    </div>
    <p className="scene-body__evidence">{scene.evidencePointer}</p>
  </>
);

const LifecycleScene = ({ scene, beat }: { scene: SceneDefinition; beat: SceneBeatDefinition }) => (
  <>
    <StageCaption eyebrow="Act II · implemented" title={scene.title}>
      <p>{beat.caption}</p>
    </StageCaption>
    <div className="scene-body__lifecycle">
      {["Draft", "Artifact", "Deployment", "Run"].map((stage, i) => (
        <div key={stage} className="scene-body__lifecycle-stage">
          <span className="scene-body__lifecycle-number">{i + 1}</span>
          <strong>{stage}</strong>
          {i < 3 && <span className="scene-body__lifecycle-arrow">→</span>}
        </div>
      ))}
    </div>
    <p className="scene-body__evidence">{scene.evidencePointer}</p>
  </>
);

const ArchitectureScene = ({ scene, beat }: { scene: SceneDefinition; beat: SceneBeatDefinition }) => (
  <>
    <StageCaption eyebrow="Act II · implemented" title={scene.title}>
      <p>{beat.caption}</p>
    </StageCaption>
    <div className="scene-body__architecture">
      <div className="scene-body__architecture-layer">Client operations</div>
      <div className="scene-body__architecture-arrow">↓</div>
      <div className="scene-body__architecture-layer">Transport / JSON-RPC</div>
      <div className="scene-body__architecture-arrow">↓</div>
      <div className="scene-body__architecture-layer">Runtime & providers</div>
      <div className="scene-body__architecture-arrow">↓</div>
      <div className="scene-body__architecture-layer scene-body__architecture-layer--node">NodeUse</div>
    </div>
    <p className="scene-body__evidence">{scene.evidencePointer}</p>
  </>
);

const AuthoringScene = ({ scene, beat }: { scene: SceneDefinition; beat: SceneBeatDefinition }) => (
  <>
    <StageCaption eyebrow="Act II · implemented" title={scene.title}>
      <p>{beat.caption}</p>
    </StageCaption>
    <div className="scene-body__authoring">
      {["Discover", "Author", "Diagnose", "Repair"].map((step, i) => (
        <div key={step} className="scene-body__authoring-step">
          <span className="scene-body__authoring-number">{i + 1}</span>
          <strong>{step}</strong>
          {i < 3 && <span className="scene-body__authoring-arrow">→</span>}
        </div>
      ))}
    </div>
    <p className="scene-body__evidence">{scene.evidencePointer}</p>
  </>
);

const EvaluationScene = ({ scene, beat }: { scene: SceneDefinition; beat: SceneBeatDefinition }) => (
  <>
    <StageCaption eyebrow={`Act I · ${scene.claimClass}`} title={scene.title}>
      <p>{beat.caption}</p>
    </StageCaption>
    <div className="scene-body__evaluation">
      <div className="scene-body__evaluation-stat">
        <strong>36</strong>
        <span>trials</span>
      </div>
      <div className="scene-body__evaluation-stat">
        <strong>2</strong>
        <span>challenges</span>
      </div>
      <div className="scene-body__evaluation-stat">
        <strong>3</strong>
        <span>waves</span>
      </div>
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

const DemoWorkflowScene = ({
  scene,
  beat,
  demo,
  selectedNodeId,
  selectNode,
}: {
  scene: SceneDefinition;
  beat: SceneBeatDefinition;
  demo: DemoTimelineController;
  selectedNodeId: string | null;
  selectNode: (nodeId: string) => void;
}) => {
  const operationStage = operationStageByBeat[beat.id] ?? null;
  const operationEvent = operationStage
    ? demo.state.events.find((event) => event.stage === operationStage) ?? null
    : null;

  return (
    <>
      <StageCaption eyebrow="Demo" title={scene.title}>
        <p>{beat.caption}</p>
      </StageCaption>
      {operationEvent && <OperationBlock event={operationEvent} />}
      <WorkflowGraphStage selectedNodeId={selectedNodeId} selectNode={selectNode} />
      {selectedNodeId && <NodeSpotlight nodeId={selectedNodeId} close={() => selectNode("")} />}
    </>
  );
};

const assertNever = (value: never): never => {
  throw new Error(`Unexpected view: ${value}`);
};

export const SceneBody = ({ location, demo, selectedNodeId, selectNode }: SceneBodyProps) => {
  const sceneId = location.kind === "main" ? location.sceneId : "positioning";
  const beatId = location.kind === "main" ? location.beatId : "landscape";
  const scene = findScene(sceneId) ?? findScene("thesis")!;
  const beat = findBeat(sceneId, beatId) ?? scene.beats[0]!;

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
      return <ArchitectureScene scene={scene} beat={beat} />;
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
        />
      );
    case "evaluation":
      return <EvaluationScene scene={scene} beat={beat} />;
    case "conclusion":
      return <NarrativeScene scene={scene} beat={beat} />;
    default:
      return assertNever(scene.view);
  }
};
