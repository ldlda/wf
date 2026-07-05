import { useEffect, useState, type ReactNode } from "react";
import {
  fitPresentationCanvas,
  PRESENTATION_HEIGHT,
  PRESENTATION_WIDTH,
  type ViewportSize,
} from "./canvas-fit.js";

type PresentationCanvasProps = { readonly children: ReactNode };

const readViewport = (): ViewportSize => ({
  width: window.innerWidth,
  height: window.innerHeight,
});

// The fixed canvas deliberately prevents slide reflow; scenes always render
// inside a 1280×720 coordinate system and the viewport scales proportionally.
export const PresentationCanvas = ({ children }: PresentationCanvasProps) => {
  const [viewport, setViewport] = useState(readViewport);
  useEffect(() => {
    const resize = () => setViewport(readViewport());
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);
  const fit = fitPresentationCanvas(viewport);
  return (
    <div className="presentation-viewport">
      <div
        className="presentation-canvas"
        data-testid="presentation-canvas"
        style={{
          width: PRESENTATION_WIDTH,
          height: PRESENTATION_HEIGHT,
          left: fit.offsetX,
          top: fit.offsetY,
          transform: `scale(${fit.scale})`,
        }}
      >
        {children}
      </div>
    </div>
  );
};
