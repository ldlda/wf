import type { FC } from "react";
import { Cable, FileOutput, SearchCode, ShieldAlert, Terminal, Wrench, type LucideProps } from "lucide-react";
import { StageCaption } from "../StageCaption.js";
import type { SceneBeatDefinition, SceneDefinition } from "../storyboard.js";
import { evaluationEvidence, isEvaluationBeatId, type EvaluationFindingIcon } from "./evaluation-evidence.js";

type EvaluationEvidenceSceneProps = {
  readonly scene: SceneDefinition;
  readonly beat: SceneBeatDefinition;
};

const findingIcons: Record<EvaluationFindingIcon, FC<LucideProps>> = {
  schema: SearchCode,
  repair: Wrench,
  binding: Cable,
  output: FileOutput,
  shell: Terminal,
  contamination: ShieldAlert,
};

export const EvaluationEvidenceScene: FC<EvaluationEvidenceSceneProps> = ({ scene, beat }) => {
  // Unknown beat ids keep the evidence board visible rather than dropping the scene.
  const beatId = isEvaluationBeatId(beat.id) ? beat.id : "cohort";

  return (
    <>
      <StageCaption eyebrow={`Act III · ${scene.claimClass}`} title={scene.title}>
        <p>{beat.caption}</p>
      </StageCaption>
      <section
        className="evaluation-board"
        role="group"
        aria-label="evaluation evidence board"
        data-evaluation-beat={beatId}
      >
        <div className="evaluation-board__cohort" aria-label="campaign cohort equation">
          <span className="evaluation-board__cohort-total">{evaluationEvidence.totalTrials}</span>
          <span className="evaluation-board__cohort-label">audited trials</span>
          <span className="evaluation-board__cohort-equation" aria-label="cohort factors">
            {evaluationEvidence.cohortFactors.map((factor, index) => (
              <span className="evaluation-board__factor" key={factor.label}>
                {index > 0 ? " × " : ""}
                <strong>{factor.value}</strong> {factor.label}
              </span>
            ))}
          </span>
        </div>

        <ol className="evaluation-board__outcomes" aria-label="audited outcomes">
          {evaluationEvidence.outcomes.map((outcome) => (
            <li className={`evaluation-board__outcome evaluation-board__outcome--${outcome.kind}`} key={outcome.label}>
              <strong>{outcome.value}</strong>
              <span>{outcome.label}</span>
            </li>
          ))}
        </ol>

        <div className="evaluation-board__audit" aria-label="automatic and manual audit reconciliation">
          <p className="evaluation-board__section-label">Automatic grading → manual audit</p>
          {evaluationEvidence.auditCorrections.map((correction) => (
            <div className="evaluation-board__audit-row" key={correction.automatic}>
              <span>{correction.automatic}</span>
              <span aria-hidden="true">→</span>
              <strong>{correction.audited}</strong>
            </div>
          ))}
        </div>

        <ol className="evaluation-board__findings" aria-label="UX gaps exposed by trials">
          {evaluationEvidence.findings.map((finding) => {
            const Icon = findingIcons[finding.icon];
            return (
              <li className="evaluation-board__finding" key={finding.icon}>
                <Icon aria-hidden="true" />
                <span>{finding.label}</span>
              </li>
            );
          })}
        </ol>

        <p className="evaluation-board__boundary">{evaluationEvidence.validityStatement}</p>
      </section>
      <p className="scene-body__evidence">{scene.evidencePointer}</p>
    </>
  );
};
