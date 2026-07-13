import { StageCaption } from "../StageCaption.js";
import { InteractiveFigure } from "../figures/InteractiveFigure.js";
import { ARCHITECTURE_CATALOG_ID, architectureCatalog } from "../figures/architecture-catalog.js";
import type { SceneDefinition, SceneBeatDefinition } from "../storyboard.js";

const architectureCatalogs = {
  [ARCHITECTURE_CATALOG_ID]: architectureCatalog,
} as const;

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
}: ArchitectureSceneProps) => {
  // Only one catalog ships today, but resolving through the authored catalog id
  // keeps beat metadata honest and makes the next catalog addition localized.
  const catalog = beat.figure
    ? architectureCatalogs[beat.figure.catalogId as keyof typeof architectureCatalogs] ?? architectureCatalog
    : architectureCatalog;

  return (
    <section
      className="architecture-scene"
      data-testid="architecture-scene"
      data-visual-pass="architecture-stage"
      data-visual-role="primary"
      data-motion={motionDisabled ? "disabled" : "enabled"}
      data-focus-level={focusPath.length}
      data-architecture-focus={focusPath.length === 0 ? "system" : "nested"}
      data-architecture-beat={beat.id}
    >
      <StageCaption eyebrow={`Act II · ${scene.claimClass}`} title={scene.title}>
        <p>{beat.caption}</p>
      </StageCaption>
      <InteractiveFigure
        catalog={catalog}
        focusPath={focusPath}
        activeNodeId={activeNodeId}
        onFocusPathChange={onFocusPathChange}
        motionDisabled={motionDisabled}
        size="stage"
      />
    </section>
  );
};
