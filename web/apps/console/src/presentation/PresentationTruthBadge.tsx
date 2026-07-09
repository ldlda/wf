import type { PresentationTargetHealth } from "./presentation-target-status.js";

export const PresentationTruthBadge = ({
  status,
}: {
  readonly status: PresentationTargetHealth;
}) => (
  <aside
    className="presentation-truth-badge"
    data-status={status.kind}
    aria-label="presentation evidence mode"
  >
    <strong>{status.label}</strong>
    <span>{status.detail}</span>
  </aside>
);