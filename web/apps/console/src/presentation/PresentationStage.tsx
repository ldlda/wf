import type { EvidenceRecord } from "../app/state.js";
import { presentationBeats, type BeatId } from "./beats.js";
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

type PresentationStageProps = {
  readonly state: PresentationState;
  readonly demo: DemoTimelineController;
  readonly evidence: readonly EvidenceRecord[];
  readonly jump: (beat: BeatId) => void;
  readonly selectNode: (nodeId: string) => void;
  readonly clearNode: () => void;
  readonly openEvidence: () => void;
  readonly closeOverlay: () => void;
};

const operationStageByBeat: Partial<Record<BeatId, DemoEventStage>> = {
  "tool-call-start": "run_start",
  "interrupt-approval": "interrupt",
  "resume-output": "run_resume",
  "trace-evidence": "trace_read",
};

export const PresentationStage = ({
  state,
  demo,
  evidence,
  jump,
  selectNode,
  clearNode,
  openEvidence,
  closeOverlay,
}: PresentationStageProps) => {
  const beat = presentationBeats.find((candidate) => candidate.id === state.beat) ?? presentationBeats[0]!;
  const operationStage = operationStageByBeat[state.beat] ?? null;

  const operationEvent = operationStage
    ? demo.state.events.find((event) => event.stage === operationStage) ?? null
    : null;

  return (
    <div className="presentation-stage" data-beat={state.beat}>
      <OperatorChat state={state} />
      <section className="presentation-stage__main">
        <header className="presentation-stage__header">
          <StageCaption eyebrow="lda.chat defense" title={beat.title}>
            <p>{beat.caption}</p>
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
      <BeatRail activeBeat={state.beat} jump={jump} />
      <EvidenceDrawer records={evidence} mode={state.evidenceMode} close={closeOverlay} />
    </div>
  );
};
