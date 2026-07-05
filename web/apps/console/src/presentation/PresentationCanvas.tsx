import { useEffect, useState, type ReactNode } from "react";
import {
  fitPresentationCanvas,
  type ViewportSize,
} from "./canvas-fit.js";

type PresentationCanvasProps = { readonly children: ReactNode };

const readViewport = (): ViewportSize => ({
  width: window.innerWidth,
  height: window.innerHeight,
});

// The canvas adapts continuously from a 4:3 to 16:9 logical ratio while
// preserving a fixed 720px height; scenes render inside this logical
// coordinate system and the viewport scales proportionally.
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
          width: fit.logicalWidth,
          height: fit.logicalHeight,
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
