import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { Scene8ChatEntry } from "./Scene8ChatEntry.js";
import {
  initialScene8EntryState,
  scene8EntryReducer,
  type Scene8EntryAction,
  type Scene8EntryState,
} from "./scene8-entry-state.js";

afterEach(cleanup);

const renderEntry = (initialState: Scene8EntryState = initialScene8EntryState) => {
  let state = initialState;
  const dispatch = (action: Scene8EntryAction) => {
    state = scene8EntryReducer(state, action);
    rerender(<Scene8ChatEntry state={state} dispatch={dispatch} />);
  };
  const { rerender } = render(<Scene8ChatEntry state={state} dispatch={dispatch} />);
  return { dispatch };
};

describe("Scene8ChatEntry", () => {
  it("prefills the labeled composer and keeps Send enabled", () => {
    renderEntry();
    expect(screen.getByRole("textbox", { name: /authoring request/i })).toHaveValue(
      initialScene8EntryState.draft,
    );
    expect(screen.getByRole("button", { name: "Send" })).toBeEnabled();
  });

  it("updates the draft and disables Send for whitespace-only input", async () => {
    const user = userEvent.setup();
    renderEntry();
    const textarea = screen.getByRole("textbox", { name: /authoring request/i });
    await user.clear(textarea);
    await user.type(textarea, "   ");
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });

  it("reveals the first Discover group after local submission without a run action", async () => {
    const user = userEvent.setup();
    renderEntry();
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(screen.getByText(/let me inspect the available sources/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /discover.*4 tool calls/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /run prepared workflow/i })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });
});
