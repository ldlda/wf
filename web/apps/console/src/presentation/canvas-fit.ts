export const PRESENTATION_WIDTH = 1280;
export const PRESENTATION_HEIGHT = 720;

export type ViewportSize = {
  readonly width: number;
  readonly height: number;
};

export type CanvasFit = {
  readonly scale: number;
  readonly offsetX: number;
  readonly offsetY: number;
};

export const fitPresentationCanvas = (viewport: ViewportSize): CanvasFit => {
  if (viewport.width <= 0 || viewport.height <= 0) {
    return { scale: 0, offsetX: 0, offsetY: 0 };
  }
  const scale = Math.min(
    viewport.width / PRESENTATION_WIDTH,
    viewport.height / PRESENTATION_HEIGHT,
  );
  return {
    scale,
    offsetX: (viewport.width - PRESENTATION_WIDTH * scale) / 2,
    offsetY: (viewport.height - PRESENTATION_HEIGHT * scale) / 2,
  };
};
