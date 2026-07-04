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
    case "positioning":
    case "boundary":
    case "lifecycle":
    case "architecture":
    case "authoring":
    case "evaluation":
    case "conclusion":
      return <NarrativeScene scene={scene} beat={beat} />;
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
    default:
      return assertNever(scene.view);
  }
};
