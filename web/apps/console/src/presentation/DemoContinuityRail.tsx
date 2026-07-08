import type { DemoBeatLens, DemoClimaxPhase } from "./demo-workflow-model.js";

type DemoContinuityRailProps = {
  readonly lens: DemoBeatLens;
};

type RailStep = {
  readonly phase: DemoClimaxPhase;
  readonly label: string;
  readonly detail: string;
};

/* The rail shows 4 visual steps while the phase model has 5 — "resume" is
   an invisible in-between state that maps to the same rail step as "interrupt"
   for completed-index calculation but must not be marked active. */
const railSteps: ReadonlyArray<RailStep> = [
  { phase: "agent", label: "Agent request", detail: "thin interface" },
  { phase: "run", label: "Workflow run", detail: "typed runtime" },
  { phase: "interrupt", label: "Human boundary", detail: "schema-backed" },
  { phase: "evidence", label: "Evidence", detail: "traceable output" },
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
    <section className="demo-continuity-rail" aria-label="demo continuity">
      <div className="demo-continuity-rail__proof">
        <span>{lens.eyebrow}</span>
        <strong>{lens.headline}</strong>
        <code>{lens.proofLabel}</code>
      </div>
      <ol className="demo-continuity-rail__steps">
        {railSteps.map((step) => {
          const stepIndex = phaseOrder.indexOf(step.phase);
          const active = step.phase === lens.phase;
          const completed = stepIndex < currentIndex;
          return (
            <li
              key={step.phase}
              data-active={active}
              data-completed={completed}
            >
              <span>{step.label}</span>
              <small>{step.detail}</small>
            </li>
          );
        })}
      </ol>
    </section>
  );
};
