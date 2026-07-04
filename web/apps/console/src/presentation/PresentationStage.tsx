import { domAnimation, LayoutGroup, LazyMotion } from "motion/react";
import type { EvidenceRecord } from "../app/state.js";
import type { AgentMessage } from "../demo/agent/events.js";
import { SceneBody } from "./SceneBody.js";
import { SceneRail } from "./SceneRail.js";
import { DiscussionIndex } from "./DiscussionIndex.js";
import { DiscussionPanel } from "./DiscussionPanel.js";
import { EvidenceDrawer } from "./EvidenceDrawer.js";
import { OperatorChat } from "./OperatorChat.js";
import type { PresentationState } from "./presentation-state.js";
import { compositionForState } from "./presentation-state.js";
import type { DemoTimelineController } from "../demo/useDemoTimeline.js";
import { findScene, type PresentationLocation } from "./storyboard.js";

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
  readonly toggleDiscussionIndex: () => void;
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
  toggleDiscussionIndex,
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
          data-stage-theme={composition.stageTheme}
          data-chat-theme={composition.chatTheme}
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
              <>
                <SceneBody
                  location={state.location}
                  demo={demo}
                  selectedNodeId={state.selectedNodeId}
                  selectNode={selectNode}
                  openEvidence={openEvidence}
                />
                <button
                  type="button"
                  className="presentation-stage__discussion-toggle"
                  onClick={toggleDiscussionIndex}
                >
                  Discussion topics
                </button>
              </>
            )}
            {state.discussionIndexOpen && (
              <DiscussionIndex
                onSelect={(branchId) => {
                  toggleDiscussionIndex();
                  openDiscussion(branchId);
                }}
              />
            )}
            <p className="presentation-stage__mode">
              {demo.state.mode === "replay" ? "Replay" : "Live"} · {demo.state.phase}
            </p>
          </section>
          <aside className="presentation-stage__evidence" aria-label="evidence region">
            <EvidenceDrawer records={evidence} mode={composition.evidenceMode} close={closeOverlay} />
          </aside>
          <SceneRail location={state.location} jump={jump} />
        </div>
      </LayoutGroup>
    </LazyMotion>
  );
};
