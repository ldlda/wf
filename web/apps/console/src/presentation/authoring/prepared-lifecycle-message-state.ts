import type { AuthoringPhaseId } from "./authoring-recording.js";
import {
  recordingPhaseForStep,
  type PreparedLifecycleStepId,
} from "./authoring-projection.js";

export type PreparedLifecycleMessagePhase = PreparedLifecycleStepId | AuthoringPhaseId;
export type PreparedLifecycleDestinationPhase = "discover" | "validate" | "deployment";

export const PREPARED_LIFECYCLE_PHASE_PROMPTS: Readonly<Record<AuthoringPhaseId, string>> = {
  discover: "",
  draft: "Is the draft valid? Can you check and fix any issues?",
  validate: "",
  artifact: "Now save everything as a deployment and make sure the bindings are valid.",
  deployment:
    "The deployment lda_report_case_study.default is saved and valid. Shall we run it now?",
};

export const PREPARED_LIFECYCLE_PHASE_PLACEHOLDERS: Readonly<Record<AuthoringPhaseId, string>> = {
  discover: "Ask about the workflow authoring process.",
  draft: "Review the prepared draft.",
  validate: "Ask about the draft validation results.",
  artifact: "Save the validated workflow as a deployment.",
  deployment: "Ask whether the saved deployment should run.",
};

export type PreparedLifecycleSubmittedOverrides = Readonly<
  Partial<Record<PreparedLifecycleDestinationPhase, string>>
>;

export type PreparedLifecycleMessageState = {
  readonly draft: string;
  readonly submittedOverrides: PreparedLifecycleSubmittedOverrides;
  readonly runRequested: string | null;
};

export const initialPreparedLifecycleMessageState: PreparedLifecycleMessageState = {
  draft: "",
  submittedOverrides: {},
  runRequested: null,
};

export type PreparedLifecycleMessageAction =
  | { readonly type: "draft_edited"; readonly draft: string }
  | { readonly type: "discover_submitted" }
  | { readonly type: "draft_submitted" }
  | { readonly type: "artifact_submitted" }
  | { readonly type: "run_requested" };

const hasText = (text: string): boolean => text.trim().length > 0;

const submitOverride = (
  state: PreparedLifecycleMessageState,
  destination: PreparedLifecycleDestinationPhase,
): PreparedLifecycleMessageState => {
  if (!hasText(state.draft) || state.submittedOverrides[destination] !== undefined) return state;

  return {
    ...state,
    // The submitted text is preserved in the transcript override; leaving it
    // in the composer would leak the previous phase's request into the next.
    draft: "",
    submittedOverrides: {
      ...state.submittedOverrides,
      [destination]: state.draft,
    },
  };
};

export const preparedLifecycleMessageReducer = (
  state: PreparedLifecycleMessageState,
  action: PreparedLifecycleMessageAction,
): PreparedLifecycleMessageState => {
  switch (action.type) {
    case "draft_edited":
      return state.runRequested === null ? { ...state, draft: action.draft } : state;
    case "discover_submitted":
      return submitOverride(state, "discover");
    case "draft_submitted":
      return submitOverride(state, "validate");
    case "artifact_submitted":
      return submitOverride(state, "deployment");
    case "run_requested":
      return state.runRequested === null && hasText(state.draft)
        ? { ...state, draft: "", runRequested: state.draft }
        : state;
  }
};

export type PreparedLifecycleMessageProjection = {
  readonly draft: string;
  readonly prefill: string;
  readonly placeholder: string;
};

export const projectPreparedLifecycleMessage = (
  state: PreparedLifecycleMessageState,
  step: PreparedLifecycleMessagePhase,
): PreparedLifecycleMessageProjection => {
  const phase = recordingPhaseForStep(step);
  return {
    draft: state.draft,
    prefill: PREPARED_LIFECYCLE_PHASE_PROMPTS[phase],
    placeholder: PREPARED_LIFECYCLE_PHASE_PLACEHOLDERS[phase],
  };
};

/** Returns the transcript-facing request overrides by destination phase. */
export const projectPreparedLifecycleSubmittedOverrides = (
  state: PreparedLifecycleMessageState,
): PreparedLifecycleSubmittedOverrides => state.submittedOverrides;
