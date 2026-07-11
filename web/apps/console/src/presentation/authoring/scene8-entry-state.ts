export const SCENE8_REQUEST =
  "We need to author a report workflow for the lda_report scenario. What sources and capabilities are available?";

export type Scene8EntryState =
  | { readonly phase: "empty"; readonly draft: string }
  | { readonly phase: "submitted"; readonly draft: string; readonly request: string };

export type Scene8EntryAction =
  | { readonly type: "draft_changed"; readonly draft: string }
  | { readonly type: "submit" };

export const initialScene8EntryState: Scene8EntryState = {
  phase: "empty",
  draft: SCENE8_REQUEST,
};

export const canSubmitScene8Entry = (state: Scene8EntryState): boolean =>
  state.phase === "empty" && state.draft.trim().length > 0;

export const scene8EntryReducer = (
  state: Scene8EntryState,
  action: Scene8EntryAction,
): Scene8EntryState => {
  if (state.phase === "submitted") return state;

  switch (action.type) {
    case "draft_changed":
      return { phase: "empty", draft: action.draft };
    case "submit":
      return canSubmitScene8Entry(state)
        ? { phase: "submitted", draft: state.draft, request: state.draft }
        : state;
  }
};
