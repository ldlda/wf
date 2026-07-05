import { findScene, mainScenes, type MainLocation } from "./storyboard.js";

type SceneProgressProps = {
  readonly location: MainLocation;
};

export const SceneProgress = ({ location }: SceneProgressProps) => {
  const scene = findScene(location.sceneId);
  const sceneIndex = mainScenes.findIndex((s) => s.id === location.sceneId);
  const totalScenes = mainScenes.length;
  const beatIndex = scene?.beats.findIndex((b) => b.id === location.beatId) ?? -1;
  const totalBeats = scene?.beats.length ?? 0;

  return (
    <p className="scene-progress" aria-label="scene position">
      {sceneIndex >= 0 && (
        <span className="scene-progress__scene">
          {sceneIndex + 1} / {totalScenes}
        </span>
      )}
      {totalBeats > 1 && (
        <span className="scene-progress__beat">
          {beatIndex >= 0 ? beatIndex + 1 : 1} / {totalBeats}
        </span>
      )}
    </p>
  );
};
