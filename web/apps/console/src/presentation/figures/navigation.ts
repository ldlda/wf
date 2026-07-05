import type { PositionedFigure } from "./layout.js";

export type FigureDirection = "ArrowUp" | "ArrowDown" | "ArrowLeft" | "ArrowRight";

export const nextFigureNodeId = (
  figure: PositionedFigure,
  currentNodeId: string,
  direction: FigureDirection,
): string => {
  const current = figure.nodes.find((node) => node.id === currentNodeId);
  if (!current) return currentNodeId;

  const horizontal = direction === "ArrowLeft" || direction === "ArrowRight";
  const sign = direction === "ArrowLeft" || direction === "ArrowUp" ? -1 : 1;

  const candidates = figure.nodes
    .filter((node) => node.id !== currentNodeId)
    .map((node) => {
      const dx = node.position.x - current.position.x;
      const dy = node.position.y - current.position.y;
      return {
        id: node.id,
        primary: horizontal ? dx * sign : dy * sign,
        secondary: Math.abs(horizontal ? dy : dx),
      };
    })
    .filter((candidate) => candidate.primary > 0)
    .sort((left, right) =>
      left.primary - right.primary ||
      left.secondary - right.secondary ||
      left.id.localeCompare(right.id),
    );

  return candidates[0]?.id ?? currentNodeId;
};
