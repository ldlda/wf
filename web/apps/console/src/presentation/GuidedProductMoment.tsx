import type { DemoTimelineController } from "../demo/useDemoTimeline.js";
import type { DemoApprovalActions } from "./demo-approval-actions.js";
import { projectDemoRunFacts } from "./demo-run-facts.js";
import type {
  InterruptContractPresentation,
  OperationPresentation,
} from "./demo-workflow-model.js";
import { demoBeatLensForBeat } from "./demo-workflow-model.js";
import { InterruptDecisionForm } from "./InterruptDecisionForm.js";
import { OperationBlock } from "./OperationBlock.js";
import {
  InterruptPayloadFacts,
  RunInputFacts,
  RunOutputFacts,
  RunResumeFacts,
  RunTraceFacts,
} from "./RunFactsPanel.js";
import type { SceneBeatDefinition } from "./storyboard.js";

export type GuidedProductMomentProps = {
  readonly beat: SceneBeatDefinition;
  readonly demo: DemoTimelineController;
  readonly contract: InterruptContractPresentation | null;
  readonly operation: OperationPresentation | null;
  readonly approvalActions?: DemoApprovalActions | undefined;
  readonly openEvidence: () => void;
};

const momentForBeat = (beatId: string): "approval" | "resume" | "output" | "trace" =>
  beatId === "resume" || beatId === "output" || beatId === "trace" ? beatId : "approval";

const statusCopy = (
  moment: ReturnType<typeof momentForBeat>,
  approvalActions?: DemoApprovalActions,
): string => {
  if (moment !== "approval") return "Same persisted run; inspect the proof below.";
  if (approvalActions?.state === "submitted") return "Submitted. Same run resumed.";
  if (approvalActions?.state === "cancelled") {
    return "Cancelled in presentation replay. No resume evidence is shown.";
  }
  return "Run is paused. Submit resumes this same run.";
};

export const GuidedProductMoment = ({
  beat,
  demo,
  contract,
  operation,
  approvalActions,
  openEvidence,
}: GuidedProductMomentProps) => {
  const moment = momentForBeat(beat.id);
  const lens = demoBeatLensForBeat(beat.id);
  const facts = projectDemoRunFacts(demo);
  const runResume = demo.state.events.find((event) => event.stage === "run_resume");

  return (
    <section className="guided-product-moment" aria-label="current product moment" data-moment={moment}>
      <header className="guided-product-moment__header">
        <span>{lens.eyebrow}</span>
        <strong>{lens.headline}</strong>
        <p>{statusCopy(moment, approvalActions)}</p>
      </header>

      <div className="guided-product-moment__primary">
        {moment === "approval" && contract ? (
          <div className="guided-product-moment__approval-grid">
            <aside className="guided-product-moment__input-rail" aria-label="workflow input context">
              <RunInputFacts facts={facts} density="compact" />
            </aside>
            <InterruptPayloadFacts facts={facts} priority="primary" />
            <InterruptDecisionForm
              interrupt={facts.interrupt}
              runId={demo.state.events.find((e) => e.stage === "run_start")?.resultingIds.runId ?? "unknown"}
              onSubmit={(ids, comment) => approvalActions?.submit(ids, comment)}
              onCancel={() => approvalActions?.cancel()}
              terminalOutcome={approvalActions?.state === "submitted" ? "submitted" :
                approvalActions?.state === "cancelled" ? "cancelled" : undefined}
            />
          </div>
        ) : null}
        {moment === "resume" && runResume ? (
          <div className="guided-product-moment__resume-grid">
            <OperationBlock
              event={runResume}
              variant="expanded"
              openEvidence={openEvidence}
            />
            <RunResumeFacts facts={facts} />
            <RunOutputFacts facts={facts} priority="report" />
          </div>
        ) : null}
        {moment === "output" ? (
          <div className="guided-product-moment__output-grid">
            <RunOutputFacts facts={facts} priority="report" />
          </div>
        ) : null}
        {moment === "trace" ? (
          <div className="guided-product-moment__trace-grid">
            <RunTraceFacts facts={facts} />
            <RunOutputFacts facts={facts} priority="summary" />
          </div>
        ) : null}
      </div>
    </section>
  );
};
