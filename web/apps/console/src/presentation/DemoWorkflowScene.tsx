import type { DemoEvent } from "../demo/timeline/models.js";
import type { DemoTimelineController } from "../demo/useDemoTimeline.js";
import {
  demoBeatLensForBeat,
  graphExecutionForBeat,
  projectInterruptContract,
  projectOperationPresentation,
} from "./demo-workflow-model.js";
import { projectDemoRunFacts } from "./demo-run-facts.js";
import type { DemoApprovalActions } from "./demo-approval-actions.js";
import { demoSurfaceForBeat } from "./presentation-coherence.js";
import { DemoContinuityRail } from "./DemoContinuityRail.js";
import { DemoOutcomePanel } from "./DemoOutcomePanel.js";
import { GuidedProductMoment } from "./GuidedProductMoment.js";
import { InterruptContractPreview } from "./InterruptContractPreview.js";
import { NodeSpotlight } from "./NodeSpotlight.js";
import { OperationBlock } from "./OperationBlock.js";
import { RunInputFacts } from "./RunFactsPanel.js";
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
  readonly approvalActions?: DemoApprovalActions | undefined;
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
  approvalActions,
}: DemoWorkflowSceneProps) => {
  const runStart = findEvent(demo, "run_start");
  const runResume = findEvent(demo, "run_resume");
  const currentStage = operationStageByBeat[beat.id];
  const currentEvent = currentStage ? findEvent(demo, currentStage) : null;
  const contract = runStart ? projectInterruptContract(runStart, runResume) : null;
  const execution = graphExecutionForBeat(beat.id);
  const layout = layoutForBeat(beat.id);

  // Presentation-only proof labels keep the graph tied to the recorded run
  // without changing the canonical replay event payload.
  const graphVariant = beat.id === "interrupt" || beat.id === "approval" ? "compact" : "full";

  const runProof = {
    runId: runStart?.resultingIds.runId ?? null,
    planLabel: "10 plan nodes",
    traceLabel: "3 trace frames",
    evidenceLabel: "JSON-RPC evidence",
  };

  const lens = demoBeatLensForBeat(beat.id);
  const currentOperation = currentEvent ? projectOperationPresentation(currentEvent) : null;
  const facts = projectDemoRunFacts(demo);
  const surface = demoSurfaceForBeat(scene.id, beat.id);
  const showOutcomePanel = beat.id === "resume" || beat.id === "output" || beat.id === "trace";

  const showExpandedOperation = beat.id === "operation" || beat.id === "resume" || beat.id === "trace";
  const showGraph = beat.id === "graph" || beat.id === "interrupt" || beat.id === "approval" || beat.id === "output";
  const showReceipt = showGraph;
  const contractMode = beat.id === "approval"
    ? "approval"
    : beat.id === "interrupt"
      ? "preview"
      : null;

  const isGuidedDemoMoment = scene.id === "typed-human-boundary"
    || scene.id === "resume-output-evidence";

  return (
    <>
      <StageCaption eyebrow="Live system walkthrough" title={scene.title}>
        <p>{beat.caption}</p>
      </StageCaption>

      <DemoContinuityRail lens={lens} />

      <div
        className="demo-workflow-stage"
        data-beat={beat.id}
        data-demo-layout={layout}
        data-primary-surface={surface.primarySurface}
        data-support-surface={surface.supportSurface}
        aria-label="demo workflow stage"
      >
          {isGuidedDemoMoment ? (
            <GuidedProductMoment
              beat={beat}
              demo={demo}
              contract={contract}
              operation={currentOperation}
              approvalActions={approvalActions}
              openEvidence={openEvidence}
            />
          ) : (
            <>
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

              {beat.id === "input" && (
                <div className="demo-workflow-stage__input-facts">
                  <RunInputFacts facts={facts} />
                </div>
              )}

              {showGraph && (
                <div className="demo-workflow-stage__graph">
                  <WorkflowGraphStage
                    execution={execution}
                    selectedNodeId={selectedNodeId}
                    selectNode={selectNode}
                    proof={runProof}
                    variant={graphVariant}
                  />
                  {contractMode && contract && (
                    <InterruptContractPreview
                      contract={contract}
                      mode={contractMode}
                      hero={layout === "approval"}
                      approvalActions={approvalActions}
                      interrupt={facts.interrupt}
                    />
                  )}
                </div>
              )}

              {showOutcomePanel && (
                <DemoOutcomePanel
                  beatId={beat.id}
                  lens={lens}
                  operation={currentOperation}
                  contract={contract}
                />
              )}

              {showExpandedOperation && !currentEvent && (
                <div className="demo-workflow-stage__pending" role="status">
                  Replay operation is not available yet.
                </div>
              )}
            </>
          )}
      </div>

      {selectedNodeId && (
        <NodeSpotlight nodeId={selectedNodeId} close={() => selectNode(null)} />
      )}
    </>
  );
};
