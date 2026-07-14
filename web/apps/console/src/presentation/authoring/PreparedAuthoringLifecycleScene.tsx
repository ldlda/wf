import { useReducer } from "react";
import type { ReactNode } from "react";
import {
  projectPreparedLifecycleStep,
  type PreparedLifecycleStepId,
} from "./authoring-projection.js";
import { AuthoringPhaseVisual } from "./AuthoringPhaseVisual.js";
import { PresentationAssistantPane } from "./PresentationAssistantPane.js";
import {
  initialPreparedLifecycleMessageState,
  projectPreparedLifecycleMessage,
  projectPreparedLifecycleSubmittedOverrides,
  preparedLifecycleMessageReducer,
} from "./prepared-lifecycle-message-state.js";
import type { SceneBeatDefinition, SceneDefinition } from "../storyboard.js";

type PreparedAuthoringLifecycleSceneProps = {
  readonly scene: SceneDefinition;
  readonly beat: SceneBeatDefinition;
  readonly onAdvance?: (() => void) | undefined;
  readonly onRunPreparedWorkflow?: (() => Promise<void>) | undefined;
  readonly discussionRail?: ReactNode;
};

const steps = [
  { id: "discover", label: "Discover", detail: "Sources, capabilities, schemas" },
  { id: "draft", label: "Author", detail: "Create and edit mutable Draft" },
  { id: "diagnose", label: "Diagnose", detail: "Structured validation result" },
  { id: "repair", label: "Repair", detail: "Focused route edit" },
  { id: "artifact", label: "Artifact", detail: "Immutable versioned definition" },
  { id: "deployment", label: "Deployment", detail: "Bind and validate sources" },
] as const satisfies readonly {
  readonly id: PreparedLifecycleStepId;
  readonly label: string;
  readonly detail: string;
}[];

/**
 * Prepared workflow authoring lifecycle.
 *
 * Each beat shows a persistent prepared assistant beside one dominant phase
 * projection sourced from the prepared authoring recording.
 */
export const PreparedAuthoringLifecycleScene = ({ scene, beat, onAdvance, onRunPreparedWorkflow, discussionRail }: PreparedAuthoringLifecycleSceneProps) => {
  const [messageState, dispatch] = useReducer(
    preparedLifecycleMessageReducer,
    initialPreparedLifecycleMessageState,
  );
  // Storyboard beats normally match these IDs. Discovery is a safe projection
  // if a future beat reaches this scene before its authoring mapping is added.
  const activeStep = steps.find((candidate) => candidate.id === beat.id) ?? steps[0]!;
  const step = activeStep.id;
  const projection = projectPreparedLifecycleStep(step);
  const activeStepIndex = steps.findIndex((candidate) => candidate.id === step);
  return (
    <section
      className="prepared-lifecycle-scene"
      aria-label="prepared workflow authoring lifecycle"
      data-active-phase={step}
      data-recording-phase={projection.recordingPhase}
      data-primary-surface="authoring-phase"
      data-support-surface="prepared-chat"
      data-presentation-surface="editorial"
    >
      <PresentationAssistantPane
        phase={step}
        visualRole="support"
        message={projectPreparedLifecycleMessage(messageState, step)}
        submittedOverrides={projectPreparedLifecycleSubmittedOverrides(messageState)}
        runRequested={messageState.runRequested}
        onDraftChange={(draft) => dispatch({ type: "draft_edited", draft })}
        onSubmit={(submittedText) => {
          dispatch({ type: "draft_edited", draft: submittedText });
          if (step === "discover") {
            dispatch({ type: "discover_submitted" });
          }
          if (step === "draft") {
            dispatch({ type: "draft_submitted" });
            onAdvance?.();
          }
          if (step === "artifact") {
            dispatch({ type: "artifact_submitted" });
            onAdvance?.();
          }
          if (step === "deployment") {
            dispatch({ type: "run_requested" });
            // This is the same mode-aware action as the footer control; the
            // presentation remains on this beat so the presenter advances it.
            void onRunPreparedWorkflow?.();
          }
        }}
      />
      <div className="prepared-lifecycle-scene__presentation">
        <ol className="prepared-lifecycle-scene__rail" aria-label="prepared authoring lifecycle">
          {steps.map((candidate, index) => (
            <li
              key={candidate.id}
              data-active={candidate.id === step ? "true" : "false"}
              data-complete={index < activeStepIndex ? "true" : "false"}
            >
              <span className="prepared-lifecycle-scene__ordinal" aria-hidden="true">
                {String(index + 1).padStart(2, "0")}
              </span>
              <strong>{candidate.label}</strong>
              <span className="prepared-lifecycle-scene__detail">{candidate.detail}</span>
            </li>
          ))}
        </ol>

        <article
          className="prepared-lifecycle-scene__frame"
          role="region"
          aria-label="active authoring operation"
          data-authoring-step={step}
          data-recording-phase={projection.recordingPhase}
          data-visual-role="lifecycle-primary"
        >
          <header className="prepared-lifecycle-scene__frame-header">
            <div>
              <span className="prepared-lifecycle-scene__context">{scene.title}</span>
              <span className="prepared-lifecycle-scene__frame-step">{activeStep.label}</span>
              <h2>{beat.title}</h2>
              <p>{beat.caption}</p>
            </div>
            <dl className="prepared-lifecycle-scene__evidence">
              <div>
                <dt>Method</dt>
                <dd><code>{projection.primaryCommand.title}</code></dd>
              </div>
              <div>
                <dt>Equivalent CLI</dt>
                <dd><code>{projection.primaryCommand.command}</code></dd>
              </div>
            </dl>
          </header>
          {projection.evidence.kind === "diagnostic" && (
            <aside
              className="prepared-lifecycle-scene__setup-strip"
              role="note"
              aria-label={projection.evidence.faultInjection.label}
            >
              <span>Prepared setup</span>
              <strong>
                Valid revision {projection.evidence.faultInjection.fromRevision}
                {" → remove analyze.ok → "}
                invalid revision {projection.evidence.faultInjection.toRevision}
              </strong>
              <details>
                <summary>Exact command</summary>
                <code>{projection.evidence.faultInjection.command}</code>
              </details>
            </aside>
          )}
          <AuthoringPhaseVisual projection={projection} />
        </article>
      </div>
      {discussionRail && (
        <section
          className="prepared-lifecycle-scene__discussion"
          data-discussion-placement="presentation-column"
          aria-label="prepared lifecycle defense questions"
        >
          {discussionRail}
        </section>
      )}
    </section>
  );
};
