import type { EvidenceRecord } from "../app/state.js";
import type { TimelineAgentMode } from "../demo/agent/timelineAgent.js";
import { SceneProgress } from "./SceneProgress.js";
import { EvidenceReceipt } from "./evidence/EvidenceReceipt.js";
import type { DemoChromePresentation } from "./presentation-demo-chrome.js";
import { PresentationDemoRail } from "./PresentationDemoRail.js";
import type { MainLocation } from "./storyboard.js";
import { PresentationPairingPanel } from "./sync/PresentationPairingPanel.js";
import type { PresentationSyncController } from "./sync/presentation-sync-state.js";

type PresentationFooterProps = {
  readonly location: MainLocation;
  readonly evidence: readonly EvidenceRecord[];
  readonly demoRail: DemoChromePresentation;
  readonly runPreparedWorkflow?: ((mode: TimelineAgentMode) => Promise<void>) | undefined;
  readonly retryHealth: () => void;
  readonly showEvidenceReceipt: boolean;
  readonly inspectEvidence: () => void;
  readonly syncController: PresentationSyncController;
};

export const PresentationFooter = ({
  location,
  evidence,
  demoRail,
  runPreparedWorkflow,
  retryHealth,
  showEvidenceReceipt,
  inspectEvidence,
  syncController,
}: PresentationFooterProps) => (
  <footer className="presentation-footer" aria-label="presentation footer">
    <SceneProgress location={location} />
    <PresentationDemoRail
      presentation={demoRail}
      runPreparedWorkflow={runPreparedWorkflow}
      retryHealth={retryHealth}
    />
    <div className="presentation-footer__utility">
      <PresentationPairingPanel role="audience" controller={syncController} />
      <EvidenceReceipt
        records={evidence}
        visible={showEvidenceReceipt}
        onInspect={inspectEvidence}
      />
    </div>
  </footer>
);
