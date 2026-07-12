import { domAnimation, LayoutGroup, LazyMotion } from "motion/react";
import type { EvidenceRecord } from "../app/state.js";
import type { AgentMessage } from "../demo/agent/events.js";
import type { TimelineAgentController } from "../demo/agent/timelineAgent.js";
import type { DemoApprovalActions } from "./demo-approval-actions.js";
import { SceneBody } from "./SceneBody.js";
import { DiscussionPanel } from "./DiscussionPanel.js";
import { EvidenceInspector } from "./evidence/EvidenceInspector.js";
import { OperatorChat } from "./OperatorChat.js";
import { PresentationFooter } from "./PresentationFooter.js";
import type { PresentationState } from "./presentation-state.js";
import { compositionForState } from "./presentation-state.js";
import type { PresentationTargetHealth } from "./presentation-target-status.js";
import { demoChromeFor } from "./presentation-demo-chrome.js";
import type { DemoTimelineController } from "../demo/useDemoTimeline.js";
import { findScene, type MainLocation } from "./storyboard.js";

type PresentationStageProps = {
  readonly state: PresentationState;
  readonly demo: DemoTimelineController;
  readonly evidence: readonly EvidenceRecord[];
  readonly messages?: ReadonlyArray<AgentMessage>;
  readonly timelineAgent?: TimelineAgentController | undefined;
  readonly approvalActions?: DemoApprovalActions | undefined;
  readonly onApprove?: (() => void) | undefined;
  readonly onRequestRevision?: (() => void) | undefined;
  readonly targetStatus: PresentationTargetHealth;
  readonly retryHealth: () => void;
  readonly liveTargetReady: boolean;
  readonly jump: (location: MainLocation) => void;
  readonly onScene9Advance?: (() => void) | undefined;
  readonly selectNode: (nodeId: string | null) => void;
  readonly openEvidence: () => void;
  readonly closeOverlay: () => void;
  readonly openDiscussion: (branchId: string) => void;
  readonly closeDiscussion: () => void;
};

export const PresentationStage = ({
  state,
  demo,
  evidence,
  messages,
  timelineAgent,
  approvalActions,
  onApprove,
  onRequestRevision,
  targetStatus,
  retryHealth,
  liveTargetReady,
  jump,
  onScene9Advance,
  selectNode,
  openEvidence,
  closeOverlay,
  openDiscussion,
  closeDiscussion,
}: PresentationStageProps) => {
  const composition = compositionForState(state);

  const isMainScene = state.location.kind === "main";
  // Keep the footer projection pure and derive it from the same state the scene consumes.
  const demoRail = isMainScene
    ? demoChromeFor({
        sceneId: state.location.sceneId,
        phase: demo.state.phase,
        mode: demo.state.mode,
        inFlight: demo.inFlight,
        approvalState: approvalActions?.state ?? "ready",
        targetStatus,
        liveTargetReady,
        canRun: timelineAgent?.canRun ?? false,
        canRunLive: timelineAgent?.canRunLive ?? false,
      })
    : { kind: "hidden" as const };
  const activeSceneView = isMainScene
    ? findScene(state.location.sceneId)?.view ?? "unknown"
    : "discussion";

  return (
    <LazyMotion features={domAnimation}>
      <LayoutGroup id="presentation-stage">
        <div
          className="presentation-stage"
          data-chat-mode={composition.chatMode}
          data-evidence-presentation={composition.evidencePresentation}
          data-scene-view={activeSceneView}
        >
          <aside className="presentation-stage__chat" aria-label="agent chat region">
            <OperatorChat state={state} messages={messages} timelineAgent={timelineAgent} onApprove={onApprove} onRequestRevision={onRequestRevision} />
          </aside>
          <section className="presentation-stage__primary" aria-label="primary presentation region">
            {state.location.kind === "discussion" ? (
              <DiscussionPanel branchId={state.location.branchId} onClose={closeDiscussion} />
            ) : (
              <SceneBody
                location={state.location}
                demo={demo}
                timelineAgent={timelineAgent}
                selectedNodeId={state.selectedNodeId}
                selectNode={selectNode}
                openEvidence={openEvidence}
                openDiscussion={openDiscussion}
                onFocusPathChange={(path) => {
                  if (state.location.kind === "main") {
                    jump({ ...state.location, focusPath: path });
                  }
                }}
                motionDisabled={state.motionDisabled}
                approvalActions={approvalActions}
                targetStatus={targetStatus}
                retryHealth={retryHealth}
                liveTargetReady={liveTargetReady}
                onScene9Advance={onScene9Advance}
              />
            )}
          </section>
          {state.location.kind === "main" && (
            <PresentationFooter
              location={state.location}
              evidence={evidence}
              demoRail={demoRail}
              runPreparedWorkflow={timelineAgent?.runPreparedWorkflow}
              retryHealth={retryHealth}
              showEvidenceReceipt={composition.evidencePresentation !== "hidden"}
              inspectEvidence={openEvidence}
            />
          )}
          <EvidenceInspector
            records={evidence}
            open={composition.evidencePresentation === "inspector"}
            onClose={closeOverlay}
          />
        </div>
      </LayoutGroup>
    </LazyMotion>
  );
};
