import type { EvidenceRecord } from "../app/state.js";
import type { AgentMessage } from "../demo/agent/events.js";
import { BeatRail } from "./BeatRail.js";
import { EvidenceDrawer } from "./EvidenceDrawer.js";
import { NodeSpotlight } from "./NodeSpotlight.js";
import { OperationBlock } from "./OperationBlock.js";
import { OperatorChat } from "./OperatorChat.js";
import { StageCaption } from "./StageCaption.js";
import { WorkflowGraphStage } from "./WorkflowGraphStage.js";
import type { PresentationState } from "./presentation-state.js";
import type { DemoTimelineController } from "../demo/useDemoTimeline.js";
import type { DemoEventStage } from "../demo/timeline/models.js";
import { compositionForState } from "./presentation-state.js";
import { findBeat, findScene, type MainLocation, type PresentationLocation } from "./storyboard.js";

type PresentationStageProps = {
  readonly state: PresentationState;
  readonly demo: DemoTimelineController;
  readonly evidence: readonly EvidenceRecord[];
  readonly messages?: ReadonlyArray<AgentMessage>;
  readonly onApprove?: (() => void) | undefined;
  readonly onDeny?: (() => void) | undefined;
  readonly jump: (location: PresentationLocation) => void;
  readonly selectNode: (nodeId: string) => void;
  readonly clearNode: () => void;
  readonly openEvidence: () => void;
  readonly closeOverlay: () => void;
};

const operationStageByBeat: Readonly<Record<string, DemoEventStage | undefined>> = {
  operation: "run_start",
  interrupt: "interrupt",
  approval: "interrupt",
  resume: "run_resume",
  trace: "trace_read",
};

export const PresentationStage = ({
  state,
  demo,
  evidence,
  messages,
  onApprove,
  onDeny,
  jump,
  selectNode,
  clearNode,
  openEvidence,
  closeOverlay,
}: PresentationStageProps) => {
  const composition = compositionForState(state);
  const location = state.location;

  const scene =
    location.kind === "main" ? findScene(location.sceneId) : findScene("positioning");
  const beat =
    location.kind === "main" && scene
      ? scene.beats.find((b) => b.id === location.beatId)
      : scene?.beats[0];

  const operationStage = location.kind === "main" ? operationStageByBeat[location.beatId] ?? null : null;

  const operationEvent = operationStage
    ? demo.state.events.find((event) => event.stage === operationStage) ?? null
    : null;

  return (
    <div
      className="presentation-stage"
      data-stage-theme={composition.stageTheme}
      data-chat-theme={composition.chatTheme}
      data-chat-mode={composition.chatMode}
    >
      <OperatorChat state={state} messages={messages} onApprove={onApprove} onDeny={onDeny} />
      <section className="presentation-stage__main">
        <header className="presentation-stage__header">
          <StageCaption eyebrow="lda.chat defense" title={scene?.title ?? "Thesis"}>
            <p>{beat?.caption ?? ""}</p>
          </StageCaption>
          <button type="button" onClick={openEvidence}>Evidence</button>
        </header>
        {operationEvent && <OperationBlock event={operationEvent} />}
        <WorkflowGraphStage selectedNodeId={state.selectedNodeId} selectNode={selectNode} />
        {state.selectedNodeId && (
          <NodeSpotlight nodeId={state.selectedNodeId} close={clearNode} />
        )}
        <p className="presentation-stage__mode">
          {demo.state.mode === "replay" ? "Replay" : "Live"} · {demo.state.phase}
        </p>
      </section>
      <BeatRail location={location} jump={jump} />
      <EvidenceDrawer records={evidence} mode={composition.evidenceMode} close={closeOverlay} />
    </div>
  );
};
