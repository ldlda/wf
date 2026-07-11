import { describe, expect, it } from "vitest";
import {
  SCENE8_REQUEST,
  canSubmitScene8Entry,
  initialScene8EntryState,
  scene8EntryReducer,
} from "./scene8-entry-state.js";

describe("scene8EntryReducer", () => {
  it("starts with the canonical request as the editable draft", () => {
    expect(initialScene8EntryState).toEqual({ phase: "empty", draft: SCENE8_REQUEST });
    expect(canSubmitScene8Entry(initialScene8EntryState)).toBe(true);
  });

  it("updates only the draft while the entry is empty", () => {
    expect(scene8EntryReducer(initialScene8EntryState, {
      type: "draft_changed",
      draft: "A narrower request",
    })).toEqual({ phase: "empty", draft: "A narrower request" });
  });

  it("rejects whitespace-only submissions", () => {
    const state = { phase: "empty" as const, draft: "  \n\t" };
    expect(canSubmitScene8Entry(state)).toBe(false);
    expect(scene8EntryReducer(state, { type: "submit" })).toBe(state);
  });

  it("stores the exact submitted text", () => {
    const state = { phase: "empty" as const, draft: "  Keep this spacing  " };
    expect(scene8EntryReducer(state, { type: "submit" })).toEqual({
      phase: "submitted",
      draft: state.draft,
      request: state.draft,
    });
  });

  it("keeps a submitted request stable on edits or repeated submits", () => {
    const submitted = scene8EntryReducer(initialScene8EntryState, { type: "submit" });
    expect(scene8EntryReducer(submitted, {
      type: "draft_changed",
      draft: "A different request",
    })).toBe(submitted);
    expect(scene8EntryReducer(submitted, { type: "submit" })).toBe(submitted);
  });
});
