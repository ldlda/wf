import type { AuthoringPhaseId } from "./authoring-recording.js";

export type Scene9MessagePhase = AuthoringPhaseId;
export type Scene9DestinationPhase = "validate" | "deployment";

export const SCENE9_PHASE_PROMPTS: Readonly<Record<Scene9MessagePhase, string>> = {
  discover: "",
  draft: "Is the draft valid? Can you check and fix any issues?",
  validate: "",
  artifact: "Now save everything as a deployment and make sure the bindings are valid.",
  deployment:
    "The deployment lda_report_case_study.default is saved and valid. Shall we run it now?",
};

export const SCENE9_PHASE_PLACEHOLDERS: Readonly<Record<Scene9MessagePhase, string>> = {
  discover: "Ask about the workflow authoring process.",
  draft: "Review the prepared draft.",
  validate: "Ask about the draft validation results.",
  artifact: "Save the validated workflow as a deployment.",
  deployment: "Ask whether the saved deployment should run.",
};

export type Scene9SubmittedOverrides = Readonly<
  Partial<Record<Scene9DestinationPhase, string>>
>;

export type Scene9MessageState = {
  readonly draft: string;
  readonly submittedOverrides: Scene9SubmittedOverrides;
  readonly runRequested: string | null;
};

export const initialScene9MessageState: Scene9MessageState = {
  draft: "",
  submittedOverrides: {},
  runRequested: null,
};

export type Scene9MessageAction =
  | { readonly type: "draft_edited"; readonly draft: string }
  | { readonly type: "draft_submitted" }
  | { readonly type: "artifact_submitted" }
  | { readonly type: "run_requested" };

const hasText = (text: string): boolean => text.trim().length > 0;

const submitOverride = (
  state: Scene9MessageState,
  destination: Scene9DestinationPhase,
): Scene9MessageState => {
  if (!hasText(state.draft) || state.submittedOverrides[destination] !== undefined) return state;

  return {
    ...state,
    submittedOverrides: {
      ...state.submittedOverrides,
      [destination]: state.draft,
    },
  };
};

export const scene9MessageReducer = (
  state: Scene9MessageState,
  action: Scene9MessageAction,
): Scene9MessageState => {
  switch (action.type) {
    case "draft_edited":
      return state.runRequested === null ? { ...state, draft: action.draft } : state;
    case "draft_submitted":
      return submitOverride(state, "validate");
    case "artifact_submitted":
      return submitOverride(state, "deployment");
    case "run_requested":
      return state.runRequested === null && hasText(state.draft)
        ? { ...state, runRequested: state.draft }
        : state;
  }
};

export type Scene9MessageProjection = {
  readonly draft: string;
  readonly prefill: string;
  readonly placeholder: string;
};

export const projectScene9Message = (
  state: Scene9MessageState,
  phase: Scene9MessagePhase,
): Scene9MessageProjection => ({
  draft: state.draft,
  prefill: SCENE9_PHASE_PROMPTS[phase],
  placeholder: SCENE9_PHASE_PLACEHOLDERS[phase],
});

/** Keeps the transcript-facing map limited to the two staged handoff destinations. */
export const projectScene9SubmittedOverrides = (
  state: Scene9MessageState,
): Scene9SubmittedOverrides => state.submittedOverrides;
