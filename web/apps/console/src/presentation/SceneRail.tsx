import { mainScenes, type MainLocation, type PresentationLocation } from "./storyboard.js";

type SceneRailProps = {
  readonly location: PresentationLocation;
  readonly jump: (location: MainLocation) => void;
};

export const SceneRail = ({ location, jump }: SceneRailProps) => {
  const activeSceneId = location.kind === "main" ? location.sceneId : "positioning";
  return (
    <nav className="scene-rail" aria-label="presentation scene rail">
      {mainScenes.map((scene) => {
        const isActive = scene.id === activeSceneId;
        const activeBeatId =
          isActive && location.kind === "main" ? location.beatId : scene.beats[0]!.id;
        return (
          <button
            key={scene.id}
            type="button"
            data-active={isActive}
            aria-current={isActive ? "step" : undefined}
            onClick={() => jump({ kind: "main", sceneId: scene.id as MainLocation["sceneId"], beatId: scene.beats[0]!.id })}
            className="scene-rail__scene"
          >
            <span className="scene-rail__number">{scene.number}</span>
            <small className="scene-rail__title">{scene.title}</small>
            <span className="scene-rail__progress">
              {scene.beats.map((beat) => (
                <span
                  key={beat.id}
                  className={`scene-rail__beat ${beat.id === activeBeatId ? "scene-rail__beat--active" : ""}`}
                />
              ))}
            </span>
          </button>
        );
      })}
    </nav>
  );
};
