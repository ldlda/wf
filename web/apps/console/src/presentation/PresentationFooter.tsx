import type { EvidenceRecord } from "../app/state.js";
import { SceneProgress } from "./SceneProgress.js";
import { EvidenceReceipt } from "./evidence/EvidenceReceipt.js";
import type { MainLocation } from "./storyboard.js";

type PresentationFooterProps = {
  readonly location: MainLocation;
  readonly evidence: readonly EvidenceRecord[];
  readonly showEvidenceReceipt: boolean;
  readonly inspectEvidence: () => void;
};

export const PresentationFooter = ({
  location,
  evidence,
  showEvidenceReceipt,
  inspectEvidence,
}: PresentationFooterProps) => (
  <footer className="presentation-footer" aria-label="presentation footer">
    <SceneProgress location={location} />
    <EvidenceReceipt
      records={evidence}
      visible={showEvidenceReceipt}
      onInspect={inspectEvidence}
    />
  </footer>
);
