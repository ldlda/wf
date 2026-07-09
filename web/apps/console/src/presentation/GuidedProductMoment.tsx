import type { DemoTimelineController } from "../demo/useDemoTimeline.js";
import type { DemoApprovalActions } from "./demo-approval-actions.js";
import type {
  InterruptContractPresentation,
  OperationPresentation,
} from "./demo-workflow-model.js";
import { DemoOutcomePanel } from "./DemoOutcomePanel.js";
import { InterruptContractPreview } from "./InterruptContractPreview.js";
import { OperationBlock } from "./OperationBlock.js";
import type { SceneBeatDefinition } from "./storyboard.js";
import { demoBeatLensForBeat } from "./demo-workflow-model.js";

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
          <InterruptContractPreview
            contract={contract}
            mode="approval"
            hero
            approvalActions={approvalActions}
          />
        ) : null}
        {moment === "resume" && runResume ? (
          <OperationBlock
            event={runResume}
            variant="expanded"
            openEvidence={openEvidence}
          />
        ) : null}
        {(moment === "output" || moment === "trace") ? (
          <DemoOutcomePanel
            beatId={beat.id}
            lens={lens}
            operation={operation}
            contract={contract}
          />
        ) : null}
      </div>
    </section>
  );
};
