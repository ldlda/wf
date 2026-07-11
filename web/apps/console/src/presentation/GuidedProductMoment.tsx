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

const hierarchyForMoment = (moment: ReturnType<typeof momentForBeat>) => {
  switch (moment) {
    case "approval":
      return { primary: "interrupt-approval", support: "input-facts" };
    case "resume":
      return { primary: "resume-output", support: "resume-operation" };
    case "output":
      return { primary: "workflow-output", support: "none" };
    case "trace":
      return { primary: "trace-evidence", support: "output-summary" };
  }
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
  const hierarchy = hierarchyForMoment(moment);
  const lens = demoBeatLensForBeat(beat.id);
  const facts = projectDemoRunFacts(demo);
  const runResume = demo.state.events.find((event) => event.stage === "run_resume");

  return (
    <section
      className="guided-product-moment"
      aria-label="current product moment"
      data-moment={moment}
      data-primary-surface={hierarchy.primary}
      data-support-surface={hierarchy.support}
      data-approval-focus={moment === "approval" ? "decision" : undefined}
      data-continuation-focus={moment === "resume" ? "output" : moment === "trace" ? "trace" : undefined}
    >
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
            <div className="guided-product-moment__decision-column" role="region" aria-label="operator resume decision">
              <InterruptDecisionForm
                interrupt={facts.interrupt}
                runId={demo.state.events.find((e) => e.stage === "run_start")?.resultingIds.runId ?? "unknown"}
                onSubmit={approvalActions?.canSubmit ? (ids, comment) => approvalActions.submit(ids, comment) : undefined}
                onCancel={approvalActions?.canCancel ? () => approvalActions.cancel() : undefined}
                terminalOutcome={approvalActions?.state === "submitted" ? "submitted" :
                  approvalActions?.state === "cancelled" ? "cancelled" : undefined}
                showReportPreview={false}
              />
            </div>
          </div>
        ) : null}
        {moment === "resume" && runResume ? (
          <div className="guided-product-moment__resume-grid">
            <aside className="guided-product-moment__resume-support" role="region" aria-label="resume proof support">
              <OperationBlock
                event={runResume}
                variant="expanded"
                openEvidence={openEvidence}
              />
              <RunResumeFacts facts={facts} />
            </aside>
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
