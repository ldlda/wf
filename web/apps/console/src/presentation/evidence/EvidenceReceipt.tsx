import type { EvidenceRecord } from "../../app/state.js";
import { projectEvidenceReceipt } from "./evidence-model.js";

type EvidenceReceiptProps = {
  readonly records: readonly EvidenceRecord[];
  readonly visible: boolean;
  readonly onInspect: () => void;
};

export const EvidenceReceipt = ({
  records,
  visible,
  onInspect,
}: EvidenceReceiptProps) => {
  if (!visible) return null;
  const receipt = projectEvidenceReceipt(records);
  const countLabel = `${receipt.recordCount} ${receipt.recordCount === 1 ? "record" : "records"}`;
  return (
    <button
      type="button"
      className="evidence-receipt"
      aria-label="Inspect evidence"
      disabled={!receipt.available}
      onClick={onInspect}
    >
      <span>Evidence: {receipt.operation}</span>
      {receipt.status && <span data-status={receipt.status}>{receipt.status}</span>}
      <span>{countLabel}</span>
      {receipt.available && <span aria-hidden="true">Inspect</span>}
    </button>
  );
};
