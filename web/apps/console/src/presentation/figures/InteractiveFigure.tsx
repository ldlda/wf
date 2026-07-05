import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";
import type { FigureCatalogDefinition } from "./model.js";
import { layoutFigure, type PositionedFigure } from "./layout.js";
import { nextFigureNodeId, type FigureDirection } from "./navigation.js";
import {
  popFigureFocus,
  pushFigureFocus,
  resolveFigureFocus,
  type FigureFocus,
} from "./focus.js";
import { FigureBreadcrumbs } from "./FigureBreadcrumbs.js";
import { FigureNodeView } from "./FigureNodeView.js";
import "./interactive-figure.css";

type InteractiveFigureProps = {
  readonly catalog: FigureCatalogDefinition;
  readonly focusPath: readonly string[];
  readonly activeNodeId: string | null;
  readonly onFocusPathChange: (path: readonly string[]) => void;
  readonly motionDisabled: boolean;
};

export const InteractiveFigure = ({
  catalog,
  focusPath,
  activeNodeId,
  onFocusPathChange,
  motionDisabled,
}: InteractiveFigureProps) => {
  const focus = resolveFigureFocus(catalog, focusPath);
  const layout = layoutFigure(focus.figure);
  const [focusedNodeId, setFocusedNodeId] = useState<string>(
    activeNodeId ?? focus.figure.nodes[0]?.id ?? "",
  );
  const groupRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (activeNodeId) setFocusedNodeId(activeNodeId);
  }, [activeNodeId]);

  const handleExpand = useCallback(
    (nodeId: string) => {
      const next = pushFigureFocus(catalog, focus, nodeId);
      if (next.path.length > focus.path.length) {
        onFocusPathChange(next.path);
      }
    },
    [catalog, focus, onFocusPathChange],
  );

  const handleBreadcrumbNavigate = useCallback(
    (path: readonly string[]) => {
      onFocusPathChange(path);
    },
    [onFocusPathChange],
  );

  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      const key = event.key;
      if (key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        const popped = popFigureFocus(catalog, focus);
        if (popped.path.length < focus.path.length) {
          onFocusPathChange(popped.path);
        }
        return;
      }

      const directionMap: Record<string, FigureDirection> = {
        ArrowUp: "ArrowUp",
        ArrowDown: "ArrowDown",
        ArrowLeft: "ArrowLeft",
        ArrowRight: "ArrowRight",
      };

      const direction = directionMap[key];
      if (direction) {
        event.preventDefault();
        event.stopPropagation();
        const nextId = nextFigureNodeId(layout, focusedNodeId, direction);
        setFocusedNodeId(nextId);
        const nextEl = groupRef.current?.querySelector(
          `[data-testid="figure-node-${nextId}"]`,
        ) as HTMLElement | null;
        nextEl?.focus();
      }
    },
    [catalog, focus, focusedNodeId, layout, onFocusPathChange],
  );

  return (
    <div
      className="interactive-figure"
      role="group"
      aria-label={focus.figure.title}
      data-motion={motionDisabled ? "disabled" : "enabled"}
      onKeyDown={handleKeyDown}
    >
      <FigureBreadcrumbs
        breadcrumbs={focus.breadcrumbs}
        onNavigate={handleBreadcrumbNavigate}
      />
      <div className="interactive-figure__canvas" ref={groupRef}>
        {layout.nodes.map((node) => (
          <FigureNodeView
            key={node.id}
            node={node}
            isActive={node.id === activeNodeId}
            focusedNodeId={focusedNodeId}
            onActivate={() => setFocusedNodeId(node.id)}
            onExpand={handleExpand}
            onFocus={setFocusedNodeId}
          />
        ))}
        {layout.edges.map((edge) => (
          <svg
            key={edge.id}
            className="interactive-figure__edge"
            aria-hidden="true"
          >
            <line
              x1={getNodeCenter(layout, edge.from)?.x ?? 0}
              y1={getNodeCenter(layout, edge.from)?.y ?? 0}
              x2={getNodeCenter(layout, edge.to)?.x ?? 0}
              y2={getNodeCenter(layout, edge.to)?.y ?? 0}
              stroke="currentColor"
              strokeWidth={1.5}
              markerEnd="url(#figure-arrow)"
            />
          </svg>
        ))}
        <svg className="interactive-figure__edge-defs" aria-hidden="true">
          <defs>
            <marker id="figure-arrow" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
              <polygon points="0 0, 8 3, 0 6" />
            </marker>
          </defs>
        </svg>
      </div>
    </div>
  );
};

const NODE_WIDTH = 196;
const NODE_HEIGHT = 84;

const getNodeCenter = (
  layout: PositionedFigure,
  nodeId: string,
): { x: number; y: number } | undefined => {
  const node = layout.nodes.find((n) => n.id === nodeId);
  if (!node) return undefined;
  return {
    x: node.position.x + NODE_WIDTH / 2,
    y: node.position.y + NODE_HEIGHT / 2,
  };
};
