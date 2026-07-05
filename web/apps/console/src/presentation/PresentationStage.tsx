import { domAnimation, LayoutGroup, LazyMotion } from "motion/react";
import type { EvidenceRecord } from "../app/state.js";
import type { AgentMessage } from "../demo/agent/events.js";
import { SceneBody } from "./SceneBody.js";
import { DiscussionPanel } from "./DiscussionPanel.js";
import { EvidenceDrawer } from "./EvidenceDrawer.js";
import { OperatorChat } from "./OperatorChat.js";
import { SceneProgress } from "./SceneProgress.js";
import type { PresentationState } from "./presentation-state.js";
import { compositionForState } from "./presentation-state.js";
import type { DemoTimelineController } from "../demo/useDemoTimeline.js";
import { findScene, type MainLocation, type PresentationLocation } from "./storyboard.js";

type PresentationStageProps = {
  readonly state: PresentationState;
  readonly demo: DemoTimelineController;
  readonly evidence: readonly EvidenceRecord[];
  readonly messages?: ReadonlyArray<AgentMessage>;
  readonly onApprove?: (() => void) | undefined;
  readonly onDeny?: (() => void) | undefined;
  readonly jump: (location: PresentationLocation) => void;
  readonly selectNode: (nodeId: string) => void;
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
  onApprove,
  onDeny,
  jump,
  selectNode,
  openEvidence,
  closeOverlay,
  openDiscussion,
  closeDiscussion,
}: PresentationStageProps) => {
  const composition = compositionForState(state);

  const isMainScene = state.location.kind === "main";
  const activeSceneView = isMainScene
    ? findScene(state.location.sceneId)?.view ?? "unknown"
    : "discussion";

  return (
    <LazyMotion features={domAnimation}>
      <LayoutGroup id="presentation-stage">
        <div
          className="presentation-stage"
          data-chat-mode={composition.chatMode}
          data-evidence-mode={composition.evidenceMode}
          data-scene-view={activeSceneView}
        >
          <aside className="presentation-stage__chat" aria-label="agent chat region">
            <OperatorChat state={state} messages={messages} onApprove={onApprove} onDeny={onDeny} />
          </aside>
          <section className="presentation-stage__primary" aria-label="primary presentation region">
            {state.location.kind === "discussion" ? (
              <DiscussionPanel branchId={state.location.branchId} onClose={closeDiscussion} />
            ) : (
              <SceneBody
                location={state.location}
                demo={demo}
                selectedNodeId={state.selectedNodeId}
                selectNode={selectNode}
                openEvidence={openEvidence}
                onFocusPathChange={(path) => {
                  if (state.location.kind === "main") {
                    jump({ ...state.location, focusPath: path });
                  }
                }}
                motionDisabled={state.motionDisabled}
              />
            )}
          </section>
          <aside className="presentation-stage__evidence" aria-label="evidence region">
            <EvidenceDrawer records={evidence} mode={composition.evidenceMode} close={closeOverlay} />
          </aside>
          {state.location.kind === "main" && (
            <SceneProgress location={state.location} />
          )}
        </div>
      </LayoutGroup>
    </LazyMotion>
  );
};
