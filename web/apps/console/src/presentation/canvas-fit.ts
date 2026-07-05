export const PRESENTATION_MIN_WIDTH = 960;
export const PRESENTATION_MAX_WIDTH = 1280;
export const PRESENTATION_HEIGHT = 720;

export type ViewportSize = {
  readonly width: number;
  readonly height: number;
};

export type CanvasFit = {
  readonly logicalWidth: number;
  readonly logicalHeight: number;
  readonly scale: number;
  readonly offsetX: number;
  readonly offsetY: number;
};

const clamp = (value: number, minimum: number, maximum: number): number =>
  Math.min(maximum, Math.max(minimum, value));

export const fitPresentationCanvas = (viewport: ViewportSize): CanvasFit => {
  if (viewport.width <= 0 || viewport.height <= 0) {
    return {
      logicalWidth: PRESENTATION_MAX_WIDTH,
      logicalHeight: PRESENTATION_HEIGHT,
      scale: 0,
      offsetX: 0,
      offsetY: 0,
    };
  }

  // Width follows the viewport ratio only inside the reviewed 4:3-16:9 range.
  const logicalWidth = clamp(
    PRESENTATION_HEIGHT * (viewport.width / viewport.height),
    PRESENTATION_MIN_WIDTH,
    PRESENTATION_MAX_WIDTH,
  );
  const scale = Math.min(
    viewport.width / logicalWidth,
    viewport.height / PRESENTATION_HEIGHT,
  );
  return {
    logicalWidth,
    logicalHeight: PRESENTATION_HEIGHT,
    scale,
    offsetX: (viewport.width - logicalWidth * scale) / 2,
    offsetY: (viewport.height - PRESENTATION_HEIGHT * scale) / 2,
  };
};
