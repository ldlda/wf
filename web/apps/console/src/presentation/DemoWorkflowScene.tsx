import type { DemoEvent } from "../demo/timeline/models.js";
import type { DemoTimelineController } from "../demo/useDemoTimeline.js";
import {
  graphExecutionForBeat,
  projectInterruptContract,
} from "./demo-workflow-model.js";
import { InterruptContractPreview } from "./InterruptContractPreview.js";
import { NodeSpotlight } from "./NodeSpotlight.js";
import { OperationBlock } from "./OperationBlock.js";
import { StageCaption } from "./StageCaption.js";
import type { SceneBeatDefinition, SceneDefinition } from "./storyboard.js";
import { WorkflowGraphStage } from "./WorkflowGraphStage.js";

type DemoWorkflowSceneProps = {
  readonly scene: SceneDefinition;
  readonly beat: SceneBeatDefinition;
  readonly demo: DemoTimelineController;
  readonly selectedNodeId: string | null;
  readonly selectNode: (nodeId: string | null) => void;
  readonly openEvidence: () => void;
};

type DemoWorkflowLayout = "operation" | "graph" | "interrupt" | "approval" | "evidence";

const layoutForBeat = (beatId: string): DemoWorkflowLayout => {
  if (beatId === "operation" || beatId === "resume") return "operation";
  if (beatId === "interrupt") return "interrupt";
  if (beatId === "approval") return "approval";
  if (beatId === "trace" || beatId === "output") return "evidence";
  return "graph";
};

const operationStageByBeat: Readonly<Record<string, DemoEvent["stage"] | undefined>> = {
  operation: "run_start",
  resume: "run_resume",
  trace: "trace_read",
};

const findEvent = (
  demo: DemoTimelineController,
  stage: DemoEvent["stage"],
): DemoEvent | null => demo.state.events.find((event) => event.stage === stage) ?? null;

export const DemoWorkflowScene = ({
  scene,
  beat,
  demo,
  selectedNodeId,
  selectNode,
  openEvidence,
}: DemoWorkflowSceneProps) => {
  const runStart = findEvent(demo, "run_start");
  const currentStage = operationStageByBeat[beat.id];
  const currentEvent = currentStage ? findEvent(demo, currentStage) : null;
  const contract = runStart ? projectInterruptContract(runStart) : null;
  const execution = graphExecutionForBeat(beat.id);
  const layout = layoutForBeat(beat.id);

  const showExpandedOperation = beat.id === "operation" || beat.id === "resume" || beat.id === "trace";
  const showGraph = beat.id === "graph" || beat.id === "interrupt" || beat.id === "approval" || beat.id === "output";
  const showReceipt = showGraph;
  const contractMode = beat.id === "approval"
    ? "approval"
    : beat.id === "interrupt"
      ? "preview"
      : null;

  return (
    <>
      <StageCaption eyebrow="Live system walkthrough" title={scene.title}>
        <p>{beat.caption}</p>
      </StageCaption>

      <div className="demo-workflow-stage" data-beat={beat.id} data-demo-layout={layout} aria-label="demo workflow stage">
          {showExpandedOperation && currentEvent && (
            <OperationBlock
              event={currentEvent}
              variant="expanded"
              openEvidence={openEvidence}
            />
          )}

          {showReceipt && runStart && (
            <OperationBlock
              event={runStart}
              variant="receipt"
              openEvidence={openEvidence}
            />
          )}

          {showGraph && (
            <div className="demo-workflow-stage__graph">
              <WorkflowGraphStage
                execution={execution}
                selectedNodeId={selectedNodeId}
                selectNode={selectNode}
              />
              {contractMode && contract && (
                <InterruptContractPreview
                  contract={contract}
                  mode={contractMode}
                  hero={layout === "approval"}
                />
              )}
            </div>
          )}

          {showExpandedOperation && !currentEvent && (
            <div className="demo-workflow-stage__pending" role="status">
              Replay operation is not available yet.
            </div>
          )}
      </div>

      {selectedNodeId && (
        <NodeSpotlight nodeId={selectedNodeId} close={() => selectNode(null)} />
      )}
    </>
  );
};
