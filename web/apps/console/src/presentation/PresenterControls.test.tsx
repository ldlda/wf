import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PresenterControls } from "./PresenterControls.js";
import { ChatDock } from "./ChatDock.js";
import { initialPresentationState } from "./presentation-state.js";

afterEach(() => cleanup());

describe("PresenterControls", () => {
  const props = {
    state: initialPresentationState,
    next: vi.fn(),
    previous: vi.fn(),
    jump: vi.fn(),
    setStageTheme: vi.fn(),
    setChatTheme: vi.fn(),
    setChatMode: vi.fn(),
    forceReplay: vi.fn(),
    resetOverrides: vi.fn(),
    resetScene: vi.fn(),
    toggleMotion: vi.fn(),
  };

  it("changes stage and chat themes independently", async () => {
    render(<PresenterControls {...props} />);
    await userEvent.selectOptions(screen.getByLabelText(/stage theme/i), "night");
    await userEvent.selectOptions(screen.getByLabelText(/chat theme/i), "light");
    expect(props.setStageTheme).toHaveBeenCalledWith("night");
    expect(props.setChatTheme).toHaveBeenCalledWith("light");
  });

  it("forces replay without changing the current presentation location", async () => {
    render(<PresenterControls {...props} />);
    await userEvent.click(screen.getByRole("button", { name: /force replay fallback/i }));
    expect(props.forceReplay).toHaveBeenCalledTimes(1);
    expect(props.jump).not.toHaveBeenCalled();
  });
});

describe("ChatDock", () => {
  it("opens docked chat by click and keyboard", async () => {
    const openChat = vi.fn();
    render(<ChatDock openChat={openChat} />);
    await userEvent.click(screen.getByRole("button", { name: /open agent chat/i }));
    expect(openChat).toHaveBeenCalledTimes(1);
  });
});
