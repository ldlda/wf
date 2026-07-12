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
        data-evaluation-focus={beatId}
        data-evaluation-layout={beatId === "findings" ? "3x2-with-evidence-strip" : "campaign-audit-board"}
        data-visual-role="evaluation-summary"
        data-presentation-surface="editorial"
      >
        <div className="evaluation-board__campaign-strip" role="group" aria-label="campaign and outcome evidence strip" data-visual-role="campaign-evidence">
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
        </div>

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

        <ol className="evaluation-board__findings" aria-label="UX gaps exposed by trials" data-grid-layout="3x2">
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
