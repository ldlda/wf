import type { EvidenceRecord } from "../app/state.js";
import { SceneProgress } from "./SceneProgress.js";
import { EvidenceReceipt } from "./evidence/EvidenceReceipt.js";
import { PresentationTruthBadge } from "./PresentationTruthBadge.js";
import type { PresentationTargetHealth } from "./presentation-target-status.js";
import { isDemoChromeScene } from "./presentation-demo-chrome.js";
import type { MainLocation } from "./storyboard.js";

type PresentationFooterProps = {
  readonly location: MainLocation;
  readonly evidence: readonly EvidenceRecord[];
  readonly targetStatus: PresentationTargetHealth;
  readonly showEvidenceReceipt: boolean;
  readonly inspectEvidence: () => void;
};

export const PresentationFooter = ({
  location,
  evidence,
  targetStatus,
  showEvidenceReceipt,
  inspectEvidence,
}: PresentationFooterProps) => (
  <footer className="presentation-footer" aria-label="presentation footer">
    <SceneProgress location={location} />
    {isDemoChromeScene(location.sceneId) && <PresentationTruthBadge status={targetStatus} />}
    <EvidenceReceipt
      records={evidence}
      visible={showEvidenceReceipt}
      onInspect={inspectEvidence}
    />
  </footer>
);
