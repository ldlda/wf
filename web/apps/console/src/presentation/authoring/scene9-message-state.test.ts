import { describe, expect, it } from "vitest";
import {
  SCENE9_PHASE_PROMPTS,
  initialScene9MessageState,
  projectScene9Message,
  projectScene9SubmittedOverrides,
  scene9MessageReducer,
} from "./scene9-message-state.js";

describe("scene 9 staged message state", () => {
  it("defines the exact prompt for every phase", () => {
    expect(SCENE9_PHASE_PROMPTS).toEqual({
      discover: "",
      draft: "Is the draft valid? Can you check and fix any issues?",
      validate: "",
      artifact: "Now save everything as a deployment and make sure the bindings are valid.",
      deployment:
        "The deployment lda_report_case_study.default is saved and valid. Shall we run it now?",
    });
  });

  it("projects empty phases with a useful placeholder", () => {
    expect(projectScene9Message(initialScene9MessageState, "discover")).toMatchObject({
      draft: "",
      prefill: "",
      placeholder: expect.any(String),
    });
    expect(projectScene9Message(initialScene9MessageState, "validate")).toMatchObject({
      draft: "",
      prefill: "",
      placeholder: expect.any(String),
    });
  });

  it("projects the exact phase prefill without changing the draft", () => {
    expect(projectScene9Message(initialScene9MessageState, "draft")).toMatchObject({
      draft: "",
      prefill: SCENE9_PHASE_PROMPTS.draft,
    });
    expect(projectScene9Message(initialScene9MessageState, "artifact")).toMatchObject({
      draft: "",
      prefill: SCENE9_PHASE_PROMPTS.artifact,
    });
  });

  it("preserves edited draft text exactly when submitting draft", () => {
    const edited = scene9MessageReducer(initialScene9MessageState, {
      type: "draft_edited",
      draft: "  Check only the report binding.  ",
    });

    expect(scene9MessageReducer(edited, { type: "draft_submitted" })).toEqual({
      draft: edited.draft,
      submittedOverrides: { validate: edited.draft },
      runRequested: null,
    });
  });

  it("stores artifact submissions under the deployment destination", () => {
    const state = scene9MessageReducer(initialScene9MessageState, {
      type: "draft_edited",
      draft: "Save this edited deployment request",
    });

    expect(scene9MessageReducer(state, { type: "artifact_submitted" })).toEqual({
      draft: state.draft,
      submittedOverrides: { deployment: state.draft },
      runRequested: null,
    });
  });

  it("stores discover submissions under the discover destination", () => {
    const state = scene9MessageReducer(initialScene9MessageState, {
      type: "draft_edited",
      draft: "Inspect the report source first.",
    });

    expect(scene9MessageReducer(state, { type: "discover_submitted" })).toEqual({
      draft: state.draft,
      submittedOverrides: { discover: state.draft },
      runRequested: null,
    });
  });

  it("ignores blank submits and keeps duplicate submits idempotent", () => {
    const blank = { ...initialScene9MessageState, draft: " \n\t" };
    expect(scene9MessageReducer(blank, { type: "draft_submitted" })).toBe(blank);
    expect(scene9MessageReducer(blank, { type: "artifact_submitted" })).toBe(blank);
    expect(scene9MessageReducer(blank, { type: "run_requested" })).toBe(blank);

    const submitted = scene9MessageReducer(
      scene9MessageReducer(initialScene9MessageState, {
        type: "draft_edited",
        draft: "A draft override",
      }),
      { type: "draft_submitted" },
    );
    expect(scene9MessageReducer(submitted, { type: "draft_submitted" })).toBe(submitted);
  });

  it("records the final run request without claiming execution", () => {
    const state = scene9MessageReducer(initialScene9MessageState, {
      type: "draft_edited",
      draft: "Run this deployment",
    });
    const requested = scene9MessageReducer(state, { type: "run_requested" });

    expect(requested.runRequested).toBe("Run this deployment");
    expect(requested.submittedOverrides).toEqual({});
    expect(scene9MessageReducer(requested, { type: "run_requested" })).toBe(requested);
  });

  it("projects only destination-phase overrides for the prepared thread", () => {
    const state = {
      ...initialScene9MessageState,
      submittedOverrides: {
        validate: "Edited validation request",
        deployment: "Edited deployment request",
      },
    };

    expect(projectScene9SubmittedOverrides(state)).toEqual({
      validate: "Edited validation request",
      deployment: "Edited deployment request",
    });
  });
});
