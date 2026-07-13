import { describe, expect, it } from "vitest";
import {
  PREPARED_LIFECYCLE_PHASE_PROMPTS,
  initialPreparedLifecycleMessageState,
  projectPreparedLifecycleMessage,
  projectPreparedLifecycleSubmittedOverrides,
  preparedLifecycleMessageReducer,
} from "./prepared-lifecycle-message-state.js";

describe("prepared lifecycle staged message state", () => {
  it("defines the exact prompt for every phase", () => {
    expect(PREPARED_LIFECYCLE_PHASE_PROMPTS).toEqual({
      discover: "",
      draft: "Is the draft valid? Can you check and fix any issues?",
      validate: "",
      artifact: "Now save everything as a deployment and make sure the bindings are valid.",
      deployment:
        "The deployment lda_report_case_study.default is saved and valid. Shall we run it now?",
    });
  });

  it("projects empty phases with a useful placeholder", () => {
    expect(projectPreparedLifecycleMessage(initialPreparedLifecycleMessageState, "discover")).toMatchObject({
      draft: "",
      prefill: "",
      placeholder: expect.any(String),
    });
    expect(projectPreparedLifecycleMessage(initialPreparedLifecycleMessageState, "diagnose")).toMatchObject({
      draft: "",
      prefill: "",
      placeholder: expect.any(String),
    });
  });

  it("projects the exact phase prefill without changing the draft", () => {
    expect(projectPreparedLifecycleMessage(initialPreparedLifecycleMessageState, "draft")).toMatchObject({
      draft: "",
      prefill: PREPARED_LIFECYCLE_PHASE_PROMPTS.draft,
    });
    expect(projectPreparedLifecycleMessage(initialPreparedLifecycleMessageState, "artifact")).toMatchObject({
      draft: "",
      prefill: PREPARED_LIFECYCLE_PHASE_PROMPTS.artifact,
    });
  });

  it("preserves edited draft text exactly when submitting draft", () => {
    const edited = preparedLifecycleMessageReducer(initialPreparedLifecycleMessageState, {
      type: "draft_edited",
      draft: "  Check only the report binding.  ",
    });

    expect(preparedLifecycleMessageReducer(edited, { type: "draft_submitted" })).toEqual({
      draft: edited.draft,
      submittedOverrides: { validate: edited.draft },
      runRequested: null,
    });
  });

  it("stores artifact submissions under the deployment destination", () => {
    const state = preparedLifecycleMessageReducer(initialPreparedLifecycleMessageState, {
      type: "draft_edited",
      draft: "Save this edited deployment request",
    });

    expect(preparedLifecycleMessageReducer(state, { type: "artifact_submitted" })).toEqual({
      draft: state.draft,
      submittedOverrides: { deployment: state.draft },
      runRequested: null,
    });
  });

  it("stores discover submissions under the discover destination", () => {
    const state = preparedLifecycleMessageReducer(initialPreparedLifecycleMessageState, {
      type: "draft_edited",
      draft: "Inspect the report source first.",
    });

    expect(preparedLifecycleMessageReducer(state, { type: "discover_submitted" })).toEqual({
      draft: state.draft,
      submittedOverrides: { discover: state.draft },
      runRequested: null,
    });
  });

  it("ignores blank submits and keeps duplicate submits idempotent", () => {
    const blank = { ...initialPreparedLifecycleMessageState, draft: " \n\t" };
    expect(preparedLifecycleMessageReducer(blank, { type: "draft_submitted" })).toBe(blank);
    expect(preparedLifecycleMessageReducer(blank, { type: "artifact_submitted" })).toBe(blank);
    expect(preparedLifecycleMessageReducer(blank, { type: "run_requested" })).toBe(blank);

    const submitted = preparedLifecycleMessageReducer(
      preparedLifecycleMessageReducer(initialPreparedLifecycleMessageState, {
        type: "draft_edited",
        draft: "A draft override",
      }),
      { type: "draft_submitted" },
    );
    expect(preparedLifecycleMessageReducer(submitted, { type: "draft_submitted" })).toBe(submitted);
  });

  it("records the final run request without claiming execution", () => {
    const state = preparedLifecycleMessageReducer(initialPreparedLifecycleMessageState, {
      type: "draft_edited",
      draft: "Run this deployment",
    });
    const requested = preparedLifecycleMessageReducer(state, { type: "run_requested" });

    expect(requested.runRequested).toBe("Run this deployment");
    expect(requested.submittedOverrides).toEqual({});
    expect(preparedLifecycleMessageReducer(requested, { type: "run_requested" })).toBe(requested);
  });

  it("projects only destination-phase overrides for the prepared thread", () => {
    const state = {
      ...initialPreparedLifecycleMessageState,
      submittedOverrides: {
        validate: "Edited validation request",
        deployment: "Edited deployment request",
      },
    };

    expect(projectPreparedLifecycleSubmittedOverrides(state)).toEqual({
      validate: "Edited validation request",
      deployment: "Edited deployment request",
    });
  });
});
