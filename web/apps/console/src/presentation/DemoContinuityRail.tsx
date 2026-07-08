import type { DemoBeatLens, DemoClimaxPhase } from "./demo-workflow-model.js";

type DemoContinuityRailProps = {
  readonly lens: DemoBeatLens;
};

type RailStep = {
  readonly phase: DemoClimaxPhase;
  readonly label: string;
};

/* The rail shows 4 visual steps while the phase model has 5 — "resume" is
   an in-between state: for completed-index calculation it sits past "interrupt"
   but must not be marked active since it has no dedicated rail step. */
const railSteps: ReadonlyArray<RailStep> = [
  { phase: "agent", label: "Agent request" },
  { phase: "run", label: "Workflow run" },
  { phase: "interrupt", label: "Human boundary" },
  { phase: "evidence", label: "Evidence" },
];

const phaseOrder: ReadonlyArray<DemoClimaxPhase> = [
  "agent",
  "run",
  "interrupt",
  "resume",
  "evidence",
];

export const DemoContinuityRail = ({ lens }: DemoContinuityRailProps) => {
  const currentIndex = phaseOrder.indexOf(lens.phase);

  return (
    <nav className="demo-continuity-rail" aria-label="demo continuity">
      <ol className="demo-continuity-rail__steps">
        {railSteps.map((step, idx) => {
          const stepIndex = phaseOrder.indexOf(step.phase);
          const active = step.phase === lens.phase;
          const completed = stepIndex < currentIndex;
          const isLast = idx === railSteps.length - 1;
          return (
            <li key={step.phase}>
              {!isLast && <span className="demo-continuity-rail__connector" data-completed={completed || active} />}
              <span
                className="demo-continuity-rail__dot"
                data-active={active}
                data-completed={completed}
              />
              <span className="demo-continuity-rail__label" data-active={active} data-completed={completed}>
                {step.label}
              </span>
            </li>
          );
        })}
      </ol>
      <code className="demo-continuity-rail__beat-code">{lens.proofLabel}</code>
    </nav>
  );
};
