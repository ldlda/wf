import type { ReactNode } from "react";

type PresentationCanvasProps = {
  readonly children: ReactNode;
};

export const PresentationCanvas = ({ children }: PresentationCanvasProps) => (
  <div className="presentation-viewport">
    {/*
      Keep the presentation as normal responsive DOM instead of scaling the
      whole stage with transform: scale(...). React Flow and future floating UI
      measure DOM geometry; transformed ancestors make those measurements lie.
      The 12:9-16:9 stage ratio is enforced by CSS on this element.
    */}
    <div
      className="presentation-canvas"
      data-testid="presentation-canvas"
    >
      {children}
    </div>
  </div>
);
