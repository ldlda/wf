import { StageCaption } from "../StageCaption.js";
import { InteractiveFigure } from "../figures/InteractiveFigure.js";
import { architectureCatalog } from "../figures/architecture-catalog.js";

type ArchitectureSceneProps = {
  readonly focusPath: readonly string[];
  readonly activeNodeId: string | null;
  readonly onFocusPathChange: (path: readonly string[]) => void;
  readonly motionDisabled: boolean;
};

export const ArchitectureScene = ({
  focusPath,
  activeNodeId,
  onFocusPathChange,
  motionDisabled,
}: ArchitectureSceneProps) => (
  <>
    <StageCaption eyebrow="Act II · implemented" title="Architecture Zoom">
      <p>The system exposes one public lifecycle surface across all client types.</p>
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
