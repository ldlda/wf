import { mainScenes, type PresentationLocation } from "./storyboard.js";

type BeatRailProps = {
  readonly location: PresentationLocation;
  readonly jump: (location: PresentationLocation) => void;
};

export const BeatRail = ({ location, jump }: BeatRailProps) => {
  const activeSceneId = location.kind === "main" ? location.sceneId : "positioning";
  return (
    <nav className="beat-rail" aria-label="presentation beat rail">
      {mainScenes.map((scene) => {
        const firstBeat = scene.beats[0]!;
        const isActive = scene.id === activeSceneId;
        return (
          <button
            key={scene.id}
            type="button"
            data-active={isActive}
            aria-current={isActive ? "step" : undefined}
            onClick={() => jump({ kind: "main", sceneId: scene.id, beatId: firstBeat.id })}
          >
            <span>{scene.number}</span>
            <small>{scene.title}</small>
          </button>
        );
      })}
    </nav>
  );
};
