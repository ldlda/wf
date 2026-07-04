import { useEffect, useRef } from "react";
import type { PresentationState } from "./presentation-state.js";
import { compositionForState } from "./presentation-state.js";
import type { ChatMode, ChatTheme, MainLocation, PresentationLocation, StageTheme } from "./storyboard.js";
import { findScene, mainScenes } from "./storyboard.js";

type PresenterControlsProps = {
  readonly state: PresentationState;
  readonly next: () => void;
  readonly previous: () => void;
  readonly jump: (location: PresentationLocation) => void;
  readonly setStageTheme: (theme: StageTheme | null) => void;
  readonly setChatTheme: (theme: ChatTheme | null) => void;
  readonly setChatMode: (mode: ChatMode | null) => void;
  readonly forceReplay: () => void;
  readonly openDiscussionIndex: () => void;
  readonly resetOverrides: () => void;
};

export const PresenterControls = ({
  state,
  next,
  previous,
  jump,
  setStageTheme,
  setChatTheme,
  setChatMode,
  forceReplay,
  openDiscussionIndex,
  resetOverrides,
}: PresenterControlsProps) => {
  const composition = compositionForState(state);
  const isMain = state.location.kind === "main";
  const currentScene = isMain ? findScene(state.location.sceneId) : null;
  const currentBeat = currentScene?.beats.find((b) => b.id === (state.location as MainLocation).beatId);

  return (
    <div className="presenter-controls" role="dialog" aria-label="presenter controls">
      <div className="presenter-controls__nav">
        <button type="button" onClick={previous}>Previous</button>
        <button type="button" onClick={next}>Next</button>
      </div>
      <div className="presenter-controls__info">
        <span>{currentScene?.title ?? "Discussion"}</span>
        {currentBeat && <span> · {currentBeat.title}</span>}
      </div>
      <div className="presenter-controls__over">
        <label>
          Stage theme
          <select
            value={state.stageThemeOverride ?? "scene default"}
            onChange={(e) => setStageTheme(e.target.value === "scene default" ? null : e.target.value as StageTheme)}
          >
            <option value="scene default">scene default</option>
            <option value="paper">paper</option>
            <option value="night">night</option>
          </select>
        </label>
        <label>
          Chat theme
          <select
            value={state.chatThemeOverride ?? "scene default"}
            onChange={(e) => setChatTheme(e.target.value === "scene default" ? null : e.target.value as ChatTheme)}
          >
            <option value="scene default">scene default</option>
            <option value="light">light</option>
            <option value="dark">dark</option>
          </select>
        </label>
        <label>
          Chat mode
          <select
            value={state.chatModeOverride ?? "scene default"}
            onChange={(e) => setChatMode(e.target.value === "scene default" ? null : e.target.value as ChatMode)}
          >
            <option value="scene default">scene default</option>
            <option value="hidden">hidden</option>
            <option value="full">full</option>
            <option value="rail">rail</option>
            <option value="dock">dock</option>
          </select>
        </label>
      </div>
      <div className="presenter-controls__actions">
        <span>{state.playbackMode === "replay" ? "Replay" : "Live"}</span>
        <button type="button" onClick={forceReplay}>Force replay fallback</button>
        <button type="button" onClick={openDiscussionIndex}>Open discussion index</button>
        <button type="button" onClick={resetOverrides}>Reset overrides</button>
      </div>
    </div>
  );
};
