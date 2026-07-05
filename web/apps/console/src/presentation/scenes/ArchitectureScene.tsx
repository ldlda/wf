import { StageCaption } from "../StageCaption.js";
import { InteractiveFigure } from "../figures/InteractiveFigure.js";
import { architectureCatalog } from "../figures/architecture-catalog.js";
import type { SceneDefinition, SceneBeatDefinition } from "../storyboard.js";

type ArchitectureSceneProps = {
  readonly scene: SceneDefinition;
  readonly beat: SceneBeatDefinition;
  readonly focusPath: readonly string[];
  readonly activeNodeId: string | null;
  readonly onFocusPathChange: (path: readonly string[]) => void;
  readonly motionDisabled: boolean;
};

export const ArchitectureScene = ({
  scene,
  beat,
  focusPath,
  activeNodeId,
  onFocusPathChange,
  motionDisabled,
}: ArchitectureSceneProps) => (
  <>
    <StageCaption eyebrow={`Act II · ${scene.claimClass}`} title={scene.title}>
      <p>{beat.caption}</p>
    </StageCaption>
    <InteractiveFigure
      catalog={architectureCatalog}
      focusPath={focusPath}
      activeNodeId={activeNodeId}
      onFocusPathChange={onFocusPathChange}
      motionDisabled={motionDisabled}
    />
  </>
);
