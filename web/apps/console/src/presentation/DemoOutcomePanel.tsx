import type {
  DemoBeatLens,
  InterruptContractPresentation,
  OperationPresentation,
} from "./demo-workflow-model.js";

type DemoOutcomePanelProps = {
  readonly beatId: string;
  readonly lens: DemoBeatLens;
  readonly operation: OperationPresentation | null;
  readonly contract: InterruptContractPresentation | null;
};

const outcomesText = (contract: InterruptContractPresentation | null): string =>
  contract?.outcomes.join(" / ") ?? "submitted / cancelled";

export const DemoOutcomePanel = ({
  beatId,
  lens,
  operation,
  contract,
}: DemoOutcomePanelProps) => {
  const runId = operation?.runId ?? contract?.runId ?? "run unavailable";

  if (beatId === "approval") {
    return (
      <aside className="demo-outcome-panel" aria-label="demo outcome proof">
        <span>{lens.eyebrow}</span>
        <strong>Operator sees a schema-backed request</strong>
        <dl>
          <div><dt>Run</dt><dd><code>{runId}</code></dd></div>
          <div><dt>Allowed outcomes</dt><dd>{outcomesText(contract)}</dd></div>
        </dl>
      </aside>
    );
  }

  if (beatId === "resume") {
    return (
      <aside className="demo-outcome-panel" aria-label="demo outcome proof">
        <span>{lens.eyebrow}</span>
        <strong>Same persisted run</strong>
        <dl>
          <div><dt>Run</dt><dd><code>{runId}</code></dd></div>
          <div><dt>Operation</dt><dd><code>{operation?.operation ?? lens.proofLabel}</code></dd></div>
          <div><dt>Status</dt><dd>{operation?.status ?? "completed"}</dd></div>
        </dl>
      </aside>
    );
  }

  if (beatId === "output") {
    return (
      <aside className="demo-outcome-panel" aria-label="demo outcome proof">
        <span>{lens.eyebrow}</span>
        <strong>Product state, not chat-only text</strong>
        <ul>
          <li><b>Report markdown</b><small>Generated from selected documents.</small></li>
          <li><b>Issue board changes</b><small>Created only after resume submission.</small></li>
        </ul>
      </aside>
    );
  }

  return (
    <aside className="demo-outcome-panel" aria-label="demo outcome proof">
      <span>{lens.eyebrow}</span>
      <strong>Auditable after the moment passes</strong>
      <ul>
        <li><b>Trace frames</b><small>Node-level execution history.</small></li>
        <li><b>Protocol evidence</b><small>Raw and interpreted JSON-RPC records.</small></li>
      </ul>
    </aside>
  );
};
